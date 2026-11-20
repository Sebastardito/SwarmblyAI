"""3.4: a SKILL.md is instructions from a file, never code or a permission.

The loader is deliberately stricter than YAML and reads only text: nothing is
imported, executed, compiled or added to ``sys.path``, and ``allowed-tools``
is a request that this module never grants.
"""

from __future__ import annotations

import builtins
import hashlib
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from swarmbly_app import skills
from swarmbly_app.skills import SkillError, as_prompt_block, discover, import_skill, load_skill, read_reference

DESCRIPTION = "A demo skill that explains the steps."


def _front(name: str = "demo", extra: str = "", body: str = "Follow these steps.") -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {DESCRIPTION}\n"
        "license: MIT\n"
        "compatibility: Swarmbly 3.4\n"
        "metadata:\n"
        "  owner: seb\n"
        '  version: "1"\n'
        "allowed-tools: read write\n"
        f"{extra}"
        "---\n"
        f"{body}\n"
    )


def make_skill(root: Path, name: str = "demo", *, extra: str = "",
               body: str = "Follow these steps.") -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(_front(name, extra, body), encoding="utf-8")
    return directory


def write_raw(directory: Path, raw: bytes | str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "SKILL.md"
    if isinstance(raw, bytes):
        path.write_bytes(raw)
    else:
        path.write_text(raw, encoding="utf-8")
    return directory


def test_a_valid_skill_is_read_with_its_metadata_and_hash(tmp_path: Path):
    directory = make_skill(tmp_path, body="Read the document, then answer.")
    before = list(sys.path)
    skill = load_skill(directory)

    assert skill.name == "demo"
    assert skill.description == DESCRIPTION
    assert skill.license == "MIT"
    assert skill.compatibility == "Swarmbly 3.4"
    assert skill.metadata == {"owner": "seb", "version": "1"}
    assert skill.allowed_tools == ("read", "write")
    assert skill.requested_tools == ("read", "write")
    assert "never granted" in skill.tools_note
    assert skill.body == "Read the document, then answer.\n"
    assert skill.root == directory.resolve()
    assert len(skill.sha256) == 64 and all(c in "0123456789abcdef" for c in skill.sha256)
    assert skill.sha256 == hashlib.sha256((directory / "SKILL.md").read_bytes()).hexdigest()
    assert skill.warnings == []
    assert skill.ignored == {}
    assert skill.manifest is None
    assert list(sys.path) == before


def test_quoted_scalars_and_a_deep_metadata_quote(tmp_path: Path):
    directory = tmp_path / "demo"
    write_raw(directory, (
        "---\n"
        "name: demo\n"
        'description: "A: demo, not a comment # really"\n'
        "license: 'MIT'\n"
        "metadata:\n"
        "  owner: 'O''Brien'\n"
        "  note: \"line\\nnext\"\n"
        "---\n"
        "Body.\n"
    ))
    skill = load_skill(directory)
    assert skill.description == "A: demo, not a comment # really"
    assert skill.license == "MIT"
    assert skill.metadata == {"owner": "O'Brien", "note": "line\nnext"}
    assert skill.allowed_tools == ()


def test_unknown_top_level_keys_are_kept_ignored_with_a_warning(tmp_path: Path):
    directory = make_skill(tmp_path, extra="x-custom: something\n")
    skill = load_skill(directory)
    assert skill.ignored == {"x-custom": "something"}
    assert any("unknown frontmatter keys" in warning and "x-custom" in warning
               for warning in skill.warnings)


@pytest.mark.parametrize("name", [
    "Demo", "demo_skill", "-demo", "demo-", "de--mo", "a" * 65,
])
def test_invalid_names_are_rejected(tmp_path: Path, name: str):
    directory = tmp_path / name
    write_raw(directory, _front(name))
    with pytest.raises(SkillError):
        load_skill(directory)


def test_name_must_equal_the_directory_name(tmp_path: Path):
    directory = tmp_path / "demo"
    write_raw(directory, _front("other"))
    with pytest.raises(SkillError, match="does not match directory"):
        load_skill(directory)


def test_name_boundary_is_accepted(tmp_path: Path):
    name = "a" + "b" * 62 + "c"           # 64 characters
    directory = make_skill(tmp_path, name=name)
    assert load_skill(directory).name == name


def test_description_is_required_and_capped(tmp_path: Path):
    missing = tmp_path / "demo"
    write_raw(missing, "---\nname: demo\n---\nBody\n")
    with pytest.raises(SkillError, match="description is required"):
        load_skill(missing)

    empty = tmp_path / "empty"
    write_raw(empty, '---\nname: empty\ndescription: ""\n---\nBody\n')
    with pytest.raises(SkillError, match="description is required"):
        load_skill(empty)

    too_long = tmp_path / "long"
    write_raw(too_long, f"---\nname: long\ndescription: {'x' * 1025}\n---\nBody\n")
    with pytest.raises(SkillError, match="description is longer"):
        load_skill(too_long)


def test_compatibility_is_capped(tmp_path: Path):
    directory = tmp_path / "demo"
    write_raw(directory, f"---\nname: demo\ndescription: ok\ncompatibility: {'x' * 501}\n---\nBody\n")
    with pytest.raises(SkillError, match="compatibility is longer"):
        load_skill(directory)


@pytest.mark.parametrize("extra", [
    "license: &anchor MIT\n",
    "license: *alias\n",
    "license: !custom MIT\n",
    "license: [MIT, AGPL]\n",
    "metadata: {owner: seb}\n",
    "license: |\n  MIT\n",
    "license: 123\n",
    "license: 1.5\n",
    "license: true\n",
    "license: null\n",
    "license: 2024-01-02\n",
    "license: MIT\nlicense: AGPL\n",
    "description: Another description.\n",
    "metadata:\n  owner: seb\n  owner: other\n",
    "metadata:\n  owner:\n    nested: value\n",
    "metadata:\n  owner: seb\n    version: 2\n",
    "metadata:\n\towner: seb\n",
])
def test_strict_frontmatter_rejections(tmp_path: Path, extra: str):
    directory = tmp_path / "demo"
    write_raw(directory, "---\nname: demo\ndescription: A demo.\n" + extra + "---\nBody\n")
    with pytest.raises(SkillError):
        load_skill(directory)


def test_metadata_values_must_be_strings(tmp_path: Path):
    directory = tmp_path / "demo"
    write_raw(directory, "---\nname: demo\ndescription: A demo.\nmetadata:\n  version: 1\n---\nBody\n")
    with pytest.raises(SkillError, match="must be a string"):
        load_skill(directory)


def test_bom_is_rejected_explicitly(tmp_path: Path):
    directory = tmp_path / "demo"
    write_raw(directory, b"\xef\xbb\xbf---\nname: demo\ndescription: A demo.\n---\nBody\n")
    with pytest.raises(SkillError, match="BOM"):
        load_skill(directory)


def test_invalid_utf8_skill_is_rejected(tmp_path: Path):
    directory = tmp_path / "demo"
    write_raw(directory, b"---\nname: demo\ndescription: \xff\n---\nBody\n")
    with pytest.raises(SkillError, match="UTF-8"):
        load_skill(directory)


def test_multiple_yaml_documents_are_rejected(tmp_path: Path):
    directory = tmp_path / "demo"
    write_raw(directory, (
        "---\nname: demo\ndescription: A demo.\n---\n"
        "---\nname: second\ndescription: Another.\n---\n"
    ))
    with pytest.raises(SkillError, match="multiple YAML documents"):
        load_skill(directory)


def test_frontmatter_must_be_closed(tmp_path: Path):
    directory = tmp_path / "demo"
    write_raw(directory, "---\nname: demo\ndescription: A demo.\nBody\n")
    with pytest.raises(SkillError, match="closing"):
        load_skill(directory)


def test_skill_md_is_required(tmp_path: Path):
    (tmp_path / "demo").mkdir()
    with pytest.raises(SkillError, match="missing"):
        load_skill(tmp_path / "demo")


def test_oversized_skill_md_is_rejected(tmp_path: Path):
    directory = tmp_path / "demo"
    body = "x" * (skills.MAX_SKILL_BYTES + 1)
    write_raw(directory, _front(body=body))
    with pytest.raises(SkillError, match="larger than"):
        load_skill(directory)


def test_too_many_files_is_rejected(tmp_path: Path):
    directory = make_skill(tmp_path)
    refs = directory / "references"
    refs.mkdir()
    for index in range(skills.MAX_FILES):
        (refs / f"{index}.md").write_text("x", encoding="utf-8")
    with pytest.raises(SkillError, match="too many files"):
        load_skill(directory)


def test_total_text_limit_is_rejected(tmp_path: Path):
    directory = make_skill(tmp_path)
    refs = directory / "references"
    refs.mkdir()
    chunk = b"x" * skills.MAX_REFERENCE_BYTES
    for index in range(21):                   # 21 × 100 KB > 2 MB
        (refs / f"{index}.md").write_bytes(chunk)
    with pytest.raises(SkillError, match="2 MB"):
        load_skill(directory)


def test_scripts_assets_executables_and_archives_are_ignored(tmp_path: Path):
    directory = make_skill(tmp_path)
    (directory / "references").mkdir()
    (directory / "references" / "notes.md").write_text("Notes.", encoding="utf-8")
    (directory / "scripts").mkdir()
    script = directory / "scripts" / "run.py"
    script.write_text("print('not run')\n", encoding="utf-8")
    os.chmod(script, 0o755)
    shebang = directory / "references" / "tool.md"
    shebang.write_text("#!/bin/sh\necho nope\n", encoding="utf-8")
    (directory / "assets").mkdir()
    (directory / "assets" / "logo.md").write_text("not a reference", encoding="utf-8")
    (directory / "archive.zip").write_bytes(b"PK\x03\x04secret")

    skill = load_skill(directory)
    assert skill.name == "demo"
    joined = "\n".join(skill.warnings)
    assert "scripts/run.py" in joined and "never read or run" in joined
    assert "references/tool.md" in joined and "shebang" in joined
    assert "assets/logo.md" in joined
    assert "archive.zip" in joined
    assert read_reference(skill, "references/notes.md") == "Notes."
    for bad in ("scripts/run.py", "references/tool.md", "assets/logo.md", "archive.zip"):
        with pytest.raises(SkillError):
            read_reference(skill, bad)


def test_symlink_escaping_the_root_is_rejected(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("secret", encoding="utf-8")
    directory = make_skill(tmp_path)
    (directory / "references").mkdir()
    try:
        os.symlink(outside / "secret.md", directory / "references" / "leak.md")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")
    with pytest.raises(SkillError, match="outside"):
        load_skill(directory)


def test_symlinked_directory_escaping_the_root_is_rejected(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("secret", encoding="utf-8")
    directory = make_skill(tmp_path)
    try:
        os.symlink(outside, directory / "references")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")
    with pytest.raises(SkillError, match="outside"):
        load_skill(directory)


def test_a_skill_root_symlink_is_rejected(tmp_path: Path):
    directory = make_skill(tmp_path)
    link = tmp_path / "linked"
    try:
        os.symlink(directory, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")
    with pytest.raises(SkillError, match="symlink"):
        load_skill(link)


def test_symlinks_are_never_read_even_inside_the_root(tmp_path: Path):
    directory = make_skill(tmp_path)
    (directory / "references").mkdir()
    (directory / "references" / "notes.md").write_text("Notes.", encoding="utf-8")
    try:
        os.symlink(directory / "references" / "notes.md", directory / "references" / "link.md")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")
    skill = load_skill(directory)
    assert any("ignored link references/link.md" in warning for warning in skill.warnings)
    with pytest.raises(SkillError, match="symlink"):
        read_reference(skill, "references/link.md")


def test_hardlinks_are_rejected(tmp_path: Path):
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    directory = make_skill(tmp_path)
    (directory / "references").mkdir()
    try:
        os.link(outside, directory / "references" / "hard.md")
    except (OSError, NotImplementedError):
        pytest.skip("hardlinks are not available")
    with pytest.raises(SkillError, match="hardlink"):
        load_skill(directory)


def test_read_reference_allows_root_and_references_text(tmp_path: Path):
    directory = make_skill(tmp_path)
    (directory / "EXTRA.md").write_text("Root reference.", encoding="utf-8")
    (directory / "references").mkdir()
    (directory / "references" / "notes.txt").write_text("Nested reference.", encoding="utf-8")
    (directory / "references" / "deep").mkdir()
    (directory / "references" / "deep" / "more.md").write_text("Deep.", encoding="utf-8")
    skill = load_skill(directory)
    assert read_reference(skill, "EXTRA.md") == "Root reference."
    assert read_reference(skill, "references/notes.txt") == "Nested reference."
    assert read_reference(skill, "references/deep/more.md") == "Deep."


@pytest.mark.parametrize("relpath", [
    "../outside.md",
    "references/../../outside.md",
    "/etc/hosts",
    "references/a\x00.md",
    "references\\notes.md",
    "scripts/notes.md",
    "assets/notes.md",
    "other/notes.md",
    "references/notes.py",
    "references/missing.md",
])
def test_read_reference_refuses_unsafe_or_disallowed_paths(tmp_path: Path, relpath: str):
    directory = make_skill(tmp_path)
    (directory / "references").mkdir()
    (directory / "references" / "notes.md").write_text("Notes.", encoding="utf-8")
    (directory / "scripts").mkdir()
    (directory / "scripts" / "notes.md").write_text("Script notes.", encoding="utf-8")
    (directory / "assets").mkdir()
    (directory / "assets" / "notes.md").write_text("Asset notes.", encoding="utf-8")
    (directory / "other").mkdir()
    (directory / "other" / "notes.md").write_text("Other notes.", encoding="utf-8")
    (directory / "references" / "notes.py").write_text("print(1)", encoding="utf-8")
    skill = load_skill(directory)
    with pytest.raises(SkillError):
        read_reference(skill, relpath)


def test_read_reference_refuses_oversized_invalid_utf8_bom_and_executables(tmp_path: Path):
    directory = make_skill(tmp_path)
    refs = directory / "references"
    refs.mkdir()
    (refs / "big.md").write_bytes(b"x" * (skills.MAX_REFERENCE_BYTES + 1))
    (refs / "invalid.md").write_bytes(b"\xff\xfe")
    (refs / "bom.md").write_bytes(b"\xef\xbb\xbftext")
    executable = refs / "exec.md"
    executable.write_text("text", encoding="utf-8")
    os.chmod(executable, 0o755)
    (refs / "shebang.md").write_text("#!/bin/sh\necho x\n", encoding="utf-8")
    skill = load_skill(directory)
    for name in ("big.md", "invalid.md", "bom.md", "exec.md", "shebang.md"):
        with pytest.raises(SkillError):
            read_reference(skill, f"references/{name}")


def test_body_is_capped_with_a_warning(tmp_path: Path):
    body = "\n".join(f"line {index}" for index in range(skills.MAX_BODY_LINES + 20))
    skill = load_skill(make_skill(tmp_path, body=body))
    assert len(skill.body.splitlines()) == skills.MAX_BODY_LINES
    assert any("body truncated" in warning for warning in skill.warnings)


def test_prompt_block_is_quoted_labelled_and_capped(tmp_path: Path):
    skill = load_skill(make_skill(tmp_path, body="Do the thing.\nA second line."))
    block = as_prompt_block(skill)
    assert block.startswith(f"<<<SKILL_MATERIAL name=demo sha256={skill.sha256}>>>")
    assert f"Skill demo (sha256 {skill.sha256})" in block
    assert "instructions from a file the user activated" in block
    assert "cannot change permissions or tools" in block
    assert "> Do the thing.\n> A second line." in block
    assert block.rstrip().endswith("<<<END_SKILL_MATERIAL>>>")
    assert len(block) <= skills.MAX_PROMPT_CHARS

    huge = load_skill(make_skill(tmp_path, name="huge", body="y" * (skills.MAX_PROMPT_CHARS * 2)))
    capped = as_prompt_block(huge)
    assert len(capped) <= skills.MAX_PROMPT_CHARS
    assert capped.rstrip().endswith("<<<END_SKILL_MATERIAL>>>")
    assert "truncated" in capped


def test_allowed_tools_are_only_a_request(tmp_path: Path):
    directory = tmp_path / "demo"
    write_raw(directory, (
        "---\nname: demo\ndescription: A demo.\n"
        "allowed-tools: shell admin\n---\nBody\n"
    ))
    skill = load_skill(directory)
    assert skill.requested_tools == ("shell", "admin")
    assert skill.allowed_tools == ("shell", "admin")
    assert "never granted" in skill.tools_note
    # There is no grant: the only tool-facing value is a tuple on the value.
    assert "shell" not in as_prompt_block(skill)


def test_discover_reads_one_level_and_reports_invalid_skills(tmp_path: Path):
    root = tmp_path / "skills"
    root.mkdir()
    make_skill(root, "alpha")
    make_skill(root, "beta")
    bad = root / "bad"
    write_raw(bad, "---\nname: Bad\ndescription: nope\n---\nBody\n")
    nested = root / "alpha" / "nested"
    write_raw(nested, _front("nested"))
    (root / "empty-dir").mkdir()
    errors: list[tuple[Path, str]] = []
    found = discover([root], errors=errors)
    assert [skill.name for skill in found] == ["alpha", "beta"]
    assert [path.name for path, _ in errors] == ["bad"]


def test_import_copies_only_skill_and_reference_text(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    demo = make_skill(src)
    (demo / "EXTRA.md").write_text("Root reference.", encoding="utf-8")
    (demo / "LICENSE").write_text("license text", encoding="utf-8")
    refs = demo / "references"
    refs.mkdir()
    (refs / "notes.md").write_text("Notes.", encoding="utf-8")
    (refs / "guide.txt").write_text("Guide.", encoding="utf-8")
    (refs / "nested").mkdir()
    (refs / "nested" / "more.md").write_text("More.", encoding="utf-8")
    (refs / "tool.md").write_text("#!/bin/sh\necho x\n", encoding="utf-8")
    (refs / "image.png").write_bytes(b"\x89PNG")
    scripts = demo / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text("print('never')\n", encoding="utf-8")
    assets = demo / "assets"
    assets.mkdir()
    (assets / "logo.md").write_text("asset", encoding="utf-8")

    dest = tmp_path / "dest"
    imported = import_skill(demo, dest)

    assert imported.root == (dest / "demo").resolve()
    assert imported.manifest is not None
    assert set(imported.manifest.copied) == {
        "SKILL.md", "EXTRA.md", "references/notes.md",
        "references/guide.txt", "references/nested/more.md",
    }
    ignored = dict(imported.manifest.ignored)
    assert "scripts/run.py" in ignored
    assert "assets/logo.md" in ignored
    assert "references/tool.md" in ignored
    assert "references/image.png" in ignored
    assert "LICENSE" in ignored
    for rel in imported.manifest.copied:
        assert (dest / "demo" / rel).is_file()
    assert not (dest / "demo" / "scripts").exists()
    assert not (dest / "demo" / "assets").exists()
    assert not (dest / "demo" / "references" / "tool.md").exists()
    assert imported.sha256 == load_skill(demo).sha256
    assert not any(entry.name.startswith((".demo.tmp-", ".demo.old-")) for entry in dest.iterdir())


def test_import_refuses_an_existing_name_and_overwrite_replaces_it(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    demo = make_skill(src, body="First body.")
    dest = tmp_path / "dest"
    import_skill(demo, dest)
    (dest / "demo" / "stale.md").write_text("stale", encoding="utf-8")

    with pytest.raises(SkillError, match="already exists"):
        import_skill(demo, dest)

    (demo / "SKILL.md").write_text(_front(body="Second body."), encoding="utf-8")
    replaced = import_skill(demo, dest, overwrite=True)
    assert replaced.body == "Second body.\n"
    assert not (dest / "demo" / "stale.md").exists()
    assert not any(entry.name.startswith((".demo.tmp-", ".demo.old-")) for entry in dest.iterdir())


def test_import_invalid_utf8_reference_is_ignored_not_copied(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    demo = make_skill(src)
    refs = demo / "references"
    refs.mkdir()
    (refs / "bad.md").write_bytes(b"\xff\xfe")
    imported = import_skill(demo, tmp_path / "dest")
    assert "references/bad.md" not in imported.manifest.copied
    assert "invalid" in dict(imported.manifest.ignored)["references/bad.md"]
    assert not (tmp_path / "dest" / "demo" / "references" / "bad.md").exists()


def test_load_read_prompt_and_import_never_run_anything(tmp_path: Path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    demo = make_skill(src)
    (demo / "references").mkdir()
    (demo / "references" / "notes.md").write_text("Notes.", encoding="utf-8")
    (demo / "scripts").mkdir()
    (demo / "scripts" / "payload.py").write_text("print('should never run')\n", encoding="utf-8")

    def boom(*args, **kwargs):
        raise AssertionError("skill handling tried to execute or import code")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "exec", boom)
        patch.setattr(builtins, "eval", boom)
        patch.setattr(builtins, "compile", boom)
        patch.setattr(subprocess, "run", boom)
        patch.setattr(subprocess, "Popen", boom)
        patch.setattr(subprocess, "call", boom)
        patch.setattr(subprocess, "check_call", boom)
        patch.setattr(subprocess, "check_output", boom)
        patch.setattr(importlib, "import_module", boom)
        patch.setattr(os, "system", boom)

        skill = load_skill(demo)
        assert read_reference(skill, "references/notes.md") == "Notes."
        assert any("scripts/payload.py" in warning for warning in skill.warnings)
        assert as_prompt_block(skill)
        imported = import_skill(demo, tmp_path / "dest")
        assert imported.name == "demo"
