"""Agent Skills (``SKILL.md``) read as instructions, never as code (3.4).

A skill is a directory with a ``SKILL.md`` file. Its YAML frontmatter gives a
name and a description; the Markdown after it is the body, which enters the
prompt only when the user activates the skill. References (``.md``/``.txt``
under ``references/`` or in the skill root) are read on demand. ``scripts/``,
``assets/``, executables, binaries, archives and links are never read, copied
or run.

This module is deliberately stricter than a YAML parser: it understands only
``key: value`` scalars and one level of ``metadata:`` string pairs. Anchors,
aliases, tags, flow collections, duplicate keys, non-string values, BOMs and
tabs in indentation are rejected. Unknown top-level keys are kept aside with a
warning. Loading, discovering, reading a reference and importing never import,
exec, compile, run or add anything to ``sys.path``.

``allowed-tools`` is parsed only to be shown (``requested_tools``); it never
grants a tool. The tool broker and the user's approval are the only path from
a request to a call.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

SKILL_FILE = "SKILL.md"
MAX_SKILL_BYTES = 100 * 1024
MAX_REFERENCE_BYTES = 100 * 1024
MAX_TOTAL_TEXT_BYTES = 2 * 1024 * 1024
MAX_FILES = 200
MAX_BODY_LINES = 500
MAX_PROMPT_CHARS = 20_000
MAX_DESCRIPTION_CHARS = 1024
MAX_COMPATIBILITY_CHARS = 500
MAX_NAME_CHARS = 64

ALLOWED_TOOLS_NOTE = (
    "Requested tools are shown only; they are never granted. A tool runs only "
    "through the tool broker after the user's approval."
)

_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_NUMBER_RE = re.compile(
    r"^[-+]?(?:0[xX][0-9a-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+|"
    r"(?:[0-9][0-9_]*(?:\.[0-9_]*)?|\.[0-9][0-9_]*)(?:[eE][-+]?[0-9]+)?)$"
)
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[Tt ].*)?$")
_NON_STRINGS = {"null", "~", "true", "false", "yes", "no", "on", "off", ".nan", ".inf", "-.inf", "+.inf"}
_BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".tif", ".tiff",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt",
    ".mp3", ".wav", ".ogg", ".flac", ".mp4", ".mov", ".mkv", ".webm", ".avi",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".pyc", ".pyo", ".so", ".dylib",
    ".dll", ".exe", ".bin", ".dat", ".db", ".sqlite", ".sqlite3",
}
_ARCHIVE_SUFFIXES = {
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".cab",
    ".whl", ".jar", ".war", ".apk", ".dmg", ".iso", ".zst",
}
_TEXT_SUFFIXES = {".md", ".txt"}


class SkillError(ValueError):
    """A skill could not be read, or a request would leave its root."""


@dataclass
class ImportManifest:
    """What an import copied and what it left behind, with reasons."""

    name: str
    source: str
    destination: str
    copied: tuple[str, ...] = ()
    ignored: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "destination": self.destination,
            "copied": list(self.copied),
            "ignored": [{"path": path, "reason": reason} for path, reason in self.ignored],
        }


@dataclass
class Skill:
    """A parsed skill. ``body`` is material, never policy."""

    name: str
    description: str
    body: str
    root: Path
    sha256: str
    license: str = ""
    compatibility: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    allowed_tools: tuple[str, ...] = ()
    warnings: list[str] = field(default_factory=list)
    ignored: dict[str, str] = field(default_factory=dict)
    manifest: ImportManifest | None = None
    tools_note: str = ALLOWED_TOOLS_NOTE

    @property
    def requested_tools(self) -> tuple[str, ...]:
        """Tools the skill asks for. Shown only; never granted by this module."""
        return self.allowed_tools

    @property
    def requested_tools_note(self) -> str:
        """Reminder that a requested tool still needs the broker and the user."""
        return self.tools_note

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "license": self.license,
            "compatibility": self.compatibility,
            "metadata": dict(self.metadata),
            "allowed_tools": list(self.allowed_tools),
            "requested_tools": list(self.requested_tools),
            "tools_note": self.tools_note,
            "body": self.body,
            "root": str(self.root),
            "sha256": self.sha256,
            "warnings": list(self.warnings),
            "ignored": dict(self.ignored),
            "manifest": self.manifest.to_dict() if self.manifest else None,
        }


@dataclass
class _Scan:
    text_files: list[tuple[str, Path]]
    ignored: list[tuple[str, str]]
    warnings: list[str]


# -- strict frontmatter -----------------------------------------------------

def _decode_utf8(raw: bytes, where: str) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise SkillError(f"{where}: UTF-8 BOM is not allowed")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SkillError(f"{where}: not valid UTF-8 ({exc.reason})") from None
    if "\x00" in text:
        raise SkillError(f"{where}: NUL byte is not allowed")
    if text.startswith("\ufeff"):
        raise SkillError(f"{where}: UTF-8 BOM is not allowed")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _looks_non_string(value: str) -> bool:
    low = value.lower()
    if low in _NON_STRINGS:
        return True
    if _NUMBER_RE.match(value):
        # A YAML number would become an int/float, not this format's string.
        return True
    return bool(_DATE_RE.match(value))


def _unquote(value: str, where: str) -> str:
    if value.startswith('"'):
        if len(value) < 2 or not value.endswith('"'):
            raise SkillError(f"{where}: unterminated double-quoted value")
        inner = value[1:-1]
        out: list[str] = []
        i = 0
        while i < len(inner):
            ch = inner[i]
            if ch != "\\":
                out.append(ch)
                i += 1
                continue
            i += 1
            if i >= len(inner):
                raise SkillError(f"{where}: trailing backslash in quoted value")
            esc = inner[i]
            mapping = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "r": "\r", "/": "/"}
            if esc not in mapping:
                raise SkillError(f"{where}: unsupported escape \\{esc}")
            out.append(mapping[esc])
            i += 1
        return "".join(out)
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise SkillError(f"{where}: unterminated single-quoted value")
        inner = value[1:-1]
        # In YAML single quotes, '' is one quote; a lone ' cannot occur.
        out = []
        i = 0
        while i < len(inner):
            if inner[i] == "'":
                if i + 1 < len(inner) and inner[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                raise SkillError(f"{where}: unterminated single-quoted value")
            out.append(inner[i])
            i += 1
        return "".join(out)
    return value


def _scalar(value: str, where: str) -> str:
    """One scalar, as a string. Rejects the YAML features this format forbids."""
    value = value.strip()
    if not value:
        raise SkillError(f"{where}: empty value (null is not a string)")
    quoted = value[0] in "\"'"
    if quoted:
        text = _unquote(value, where)
        if "\x00" in text:
            raise SkillError(f"{where}: NUL byte is not allowed")
        return text
    if value[0] in "[]{}&*!|>%@`,":
        raise SkillError(f"{where}: flow collections, anchors, aliases, tags and block scalars are not allowed")
    if re.search(r"(?:^|\s)[&*!]\S", value):
        raise SkillError(f"{where}: anchors, aliases and tags are not allowed")
    if ": " in value:
        raise SkillError(f"{where}: nested mappings are not allowed")
    if value in {"---", "..."}:
        raise SkillError(f"{where}: multiple YAML documents are not allowed")
    if _looks_non_string(value):
        raise SkillError(f"{where}: value must be a string (quote it if it is literal text)")
    return value


def _key_value(line: str, where: str) -> tuple[str, str]:
    key, sep, rest = line.partition(":")
    if not sep:
        raise SkillError(f"{where}: expected 'key: value'")
    key = key.strip()
    if not _KEY_RE.match(key):
        raise SkillError(f"{where}: invalid key {key!r}")
    return key, rest.strip()


def _parse_frontmatter(lines: list[str]) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    values: dict[str, str] = {}
    metadata: dict[str, str] = {}
    unknown: dict[str, str] = {}
    in_metadata = False
    metadata_indent: int | None = None

    for number, raw in enumerate(lines, start=2):
        where = f"frontmatter line {number}"
        if not raw.strip():
            continue
        leading = raw[: len(raw) - len(raw.lstrip(" \t"))]
        if "\t" in leading:
            raise SkillError(f"{where}: tabs are not allowed in indentation")
        indent = len(leading)
        if indent:
            if not in_metadata:
                raise SkillError(f"{where}: unexpected indentation (only metadata may be indented)")
            if metadata_indent is None:
                metadata_indent = indent
            elif indent != metadata_indent:
                raise SkillError(f"{where}: metadata must be one level of key: value pairs")
            key, rest = _key_value(raw[indent:], where)
            if key in metadata:
                raise SkillError(f"{where}: duplicate metadata key {key!r}")
            metadata[key] = _scalar(rest, where)
            continue

        in_metadata = False
        metadata_indent = None
        key, rest = _key_value(raw, where)
        if key in values:
            raise SkillError(f"{where}: duplicate key {key!r}")
        if key in unknown:
            raise SkillError(f"{where}: duplicate key {key!r}")
        if key == "metadata":
            if rest:
                raise SkillError(f"{where}: metadata must be an indented mapping of strings")
            in_metadata = True
            values[key] = ""
            continue
        values[key] = _scalar(rest, where)
        if key not in {"name", "description", "license", "compatibility", "allowed-tools"}:
            unknown[key] = values[key]
            del values[key]
    return values, metadata, unknown


def _split_frontmatter(text: str) -> tuple[list[str], str]:
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        raise SkillError("SKILL.md must start with a line containing only '---'")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i] == "---")
    except StopIteration:
        raise SkillError("SKILL.md frontmatter has no closing '---' line") from None
    front = lines[1:end]
    if any(line.strip() == "..." for line in front):
        raise SkillError("multiple YAML documents are not allowed")
    body_lines = lines[end + 1:]
    first = next((line for line in body_lines if line.strip()), "")
    if first == "---":
        raise SkillError("multiple YAML documents are not allowed")
    return front, "\n".join(body_lines)


# -- filesystem safety ------------------------------------------------------

def _is_junction(path: Path) -> bool:
    fn = getattr(path, "is_junction", None)
    if callable(fn):
        try:
            if fn():
                return True
        except OSError:
            pass
    if os.name == "nt":
        try:
            attrs = getattr(path.lstat(), "st_file_attributes", 0)
            reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            return bool(attrs & reparse)
        except OSError:
            return False
    return False


def _is_link(path: Path) -> bool:
    try:
        return path.is_symlink() or _is_junction(path)
    except OSError:
        return False


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _check_path_text(text: str, where: str) -> None:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        raise SkillError(f"{where}: path is not valid UTF-8") from None


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _check_not_escaping(path: Path, root: Path, where: str) -> None:
    try:
        target = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise SkillError(f"{where}: cannot resolve link ({exc})") from None
    if not _inside(target, root):
        raise SkillError(f"{where}: link points outside the skill root")


def _has_shebang(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(2) == b"#!"
    except OSError:
        return False


def _is_executable(path: Path, mode: int) -> bool:
    return bool(mode & 0o111) or _has_shebang(path)


def _looks_binary(path: Path) -> bool:
    if path.suffix.lower() in _ARCHIVE_SUFFIXES | _BINARY_SUFFIXES:
        return True
    try:
        with open(path, "rb") as handle:
            return b"\x00" in handle.read(4096)
    except OSError:
        return True


def _reason_for(path: Path, rel: str, mode: int) -> str | None:
    parts = Path(rel).parts
    if parts and parts[0] == "scripts":
        return "scripts/ is never read or run"
    if parts and parts[0] == "assets":
        return "assets/ is never read or copied"
    if _is_executable(path, mode):
        return "executable file (exec bit or shebang)"
    if path.suffix.lower() in _ARCHIVE_SUFFIXES:
        return "archive"
    if _looks_binary(path):
        return "binary or non-text file"
    allowed = (len(parts) == 1) or (parts and parts[0] == "references")
    if path.suffix.lower() in _TEXT_SUFFIXES and allowed:
        return None
    return "not a readable reference (only .md/.txt in references/ or the skill root)"


def _scan(root: Path) -> _Scan:
    text_files: list[tuple[str, Path]] = []
    ignored: list[tuple[str, str]] = []
    warnings: list[str] = []
    files = 0
    total = 0

    def walk_error(exc: OSError) -> None:
        raise SkillError(f"{root}: cannot scan ({exc})")

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=walk_error):
        here = Path(dirpath)
        if here == root:
            for special in ("scripts", "assets"):
                candidate = root / special
                if candidate.is_dir() and not _is_link(candidate):
                    reason = ("scripts/ is never read or run" if special == "scripts"
                              else "assets/ is never read or copied")
                    warnings.append(f"ignored directory {special}/: {reason}")
                    ignored.append((f"{special}/", reason))
        for name in list(dirnames):
            child = here / name
            if _is_link(child):
                rel_dir = child.relative_to(root).as_posix()
                _check_path_text(rel_dir, "directory")
                _check_not_escaping(child, root, f"directory {rel_dir}")
                warnings.append(f"ignored link directory {rel_dir}")
                ignored.append((rel_dir, "symlink or junction"))
                dirnames.remove(name)
        dirnames.sort()
        for name in sorted(filenames):
            path = here / name
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                raise SkillError(f"{path}: path escapes the skill root") from None
            _check_path_text(rel, "file")
            files += 1
            if files > MAX_FILES:
                raise SkillError(f"too many files (limit {MAX_FILES})")
            try:
                st = path.lstat()
            except OSError as exc:
                raise SkillError(f"{rel}: cannot stat ({exc})") from None
            if stat.S_ISLNK(st.st_mode) or _is_junction(path):
                _check_not_escaping(path, root, rel)
                warnings.append(f"ignored link {rel}")
                ignored.append((rel, "symlink or junction"))
                continue
            if not stat.S_ISREG(st.st_mode):
                warnings.append(f"ignored special file {rel}")
                ignored.append((rel, "not a regular file"))
                continue
            if st.st_nlink > 1:
                raise SkillError(f"{rel}: hardlinked files may point outside the skill root")
            if rel == SKILL_FILE:
                total += st.st_size
                if total > MAX_TOTAL_TEXT_BYTES:
                    raise SkillError("skill text exceeds the 2 MB total limit")
                continue
            reason = _reason_for(path, rel, st.st_mode)
            if reason is None:
                text_files.append((rel, path))
                total += st.st_size
                if total > MAX_TOTAL_TEXT_BYTES:
                    raise SkillError("skill text exceeds the 2 MB total limit")
            else:
                ignored.append((rel, reason))
                warnings.append(f"ignored {rel}: {reason}")

    return _Scan(text_files=text_files, ignored=ignored, warnings=warnings)


def _read_bytes(path: Path, limit: int, where: str) -> bytes:
    try:
        with open(path, "rb") as handle:
            raw = handle.read(limit + 1)
    except OSError as exc:
        raise SkillError(f"{where}: cannot read ({exc})") from None
    if len(raw) > limit:
        raise SkillError(f"{where}: larger than {limit} bytes")
    return raw


def load_skill(directory: str | Path) -> Skill:
    """Read and validate one skill directory. Nothing is imported or run."""
    given = Path(directory).expanduser()
    try:
        if _is_link(given):
            raise SkillError(f"{given}: skill root must not be a symlink or junction")
        if not given.is_dir():
            raise SkillError(f"{given}: not a directory")
    except OSError as exc:
        raise SkillError(f"{given}: cannot inspect ({exc})") from None
    root = given.resolve()
    skill_md = root / SKILL_FILE
    try:
        st = skill_md.lstat()
    except FileNotFoundError:
        raise SkillError(f"{root}: {SKILL_FILE} is missing") from None
    except OSError as exc:
        raise SkillError(f"{root}: cannot stat {SKILL_FILE} ({exc})") from None
    if stat.S_ISLNK(st.st_mode):
        raise SkillError(f"{SKILL_FILE}: must not be a symlink")
    if not stat.S_ISREG(st.st_mode):
        raise SkillError(f"{SKILL_FILE}: must be a regular file")
    if st.st_nlink > 1:
        raise SkillError(f"{SKILL_FILE}: hardlinked files may point outside the skill root")
    if st.st_size > MAX_SKILL_BYTES:
        raise SkillError(f"{SKILL_FILE}: larger than {MAX_SKILL_BYTES} bytes")

    raw = _read_bytes(skill_md, MAX_SKILL_BYTES, SKILL_FILE)
    text = _decode_utf8(raw, SKILL_FILE)
    front, body = _split_frontmatter(text)
    values, metadata, unknown = _parse_frontmatter(front)
    warnings: list[str] = []

    name = values.get("name", "")
    description = values.get("description", "")
    if not name:
        raise SkillError("frontmatter: name is required")
    if len(name) > MAX_NAME_CHARS or not _NAME_RE.match(name) or "--" in name:
        raise SkillError(
            "frontmatter: name must be 1-64 lowercase letters, digits or hyphens, "
            "without leading/trailing hyphens or '--'"
        )
    if name != root.name:
        raise SkillError(f"frontmatter: name {name!r} does not match directory {root.name!r}")
    if not description:
        raise SkillError("frontmatter: description is required")
    if len(description) > MAX_DESCRIPTION_CHARS:
        raise SkillError(f"frontmatter: description is longer than {MAX_DESCRIPTION_CHARS} characters")
    compatibility = values.get("compatibility", "")
    if len(compatibility) > MAX_COMPATIBILITY_CHARS:
        raise SkillError(f"frontmatter: compatibility is longer than {MAX_COMPATIBILITY_CHARS} characters")
    tools = tuple(values.get("allowed-tools", "").split())
    license_text = values.get("license", "")

    scan = _scan(root)
    warnings.extend(scan.warnings)
    if unknown:
        warnings.append("unknown frontmatter keys kept as ignored: " + ", ".join(sorted(unknown)))

    body_lines = body.splitlines()
    if len(body_lines) > MAX_BODY_LINES:
        body = "\n".join(body_lines[:MAX_BODY_LINES])
        if text.endswith("\n"):
            body += "\n"
        warnings.append(f"body truncated at {MAX_BODY_LINES} lines")

    return Skill(
        name=name,
        description=description,
        body=body,
        root=root,
        sha256=hashlib.sha256(raw).hexdigest(),
        license=license_text,
        compatibility=compatibility,
        metadata=dict(metadata),
        allowed_tools=tools,
        warnings=warnings,
        ignored=unknown,
    )


def discover(roots: str | Path | Iterable[str | Path], *,
             errors: list[tuple[Path, str]] | None = None) -> list[Skill]:
    """Skills one level below each root: ``root/<name>/SKILL.md``.

    Invalid skills are skipped; when ``errors`` is given, each rejection is
    appended as ``(path, message)`` instead of stopping discovery.
    """
    if isinstance(roots, (str, Path)):
        roots = [roots]
    found: list[Skill] = []
    for root_arg in roots:
        root = Path(root_arg).expanduser()
        try:
            if _is_link(root) or not root.is_dir():
                continue
            children = sorted(root.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for child in children:
            if _is_link(child) or not child.is_dir():
                continue
            if not (child / SKILL_FILE).is_file():
                continue
            try:
                found.append(load_skill(child))
            except SkillError as exc:
                if errors is not None:
                    errors.append((child, str(exc)))
    return found


# -- references -------------------------------------------------------------

def _relative_parts(relpath: str | Path) -> tuple[str, ...]:
    if isinstance(relpath, Path):
        text = relpath.as_posix()
    else:
        text = str(relpath)
        if "\\" in text:
            raise SkillError(f"{text!r}: backslashes are not allowed; use '/'")
    if not text or "\x00" in text:
        raise SkillError("reference path is empty or contains NUL")
    _check_path_text(text, "reference path")
    if text.startswith("/") or Path(text).is_absolute():
        raise SkillError(f"{text!r}: absolute paths are not allowed")
    parts = tuple(part for part in text.split("/") if part not in ("", "."))
    if not parts:
        raise SkillError("reference path is empty")
    if any(part == ".." for part in parts):
        raise SkillError(f"{text!r}: '..' is not allowed")
    return parts


def read_reference(skill: Skill, relpath: str | Path) -> str:
    """Read one allowed reference: ``.md``/``.txt`` under references/ or root."""
    parts = _relative_parts(relpath)
    if Path(parts[-1]).suffix.lower() not in _TEXT_SUFFIXES:
        raise SkillError(f"{relpath!s}: only .md and .txt references are readable")
    if parts[0] == "scripts" or parts[0] == "assets":
        raise SkillError(f"{relpath!s}: scripts/ and assets/ are never read")
    if len(parts) > 1 and parts[0] != "references":
        raise SkillError(f"{relpath!s}: references live under references/ or in the skill root")

    path = skill.root.joinpath(*parts)
    current = skill.root
    for part in parts:
        current = current / part
        if _is_link(current):
            raise SkillError(f"{relpath!s}: symlinks and junctions are not allowed")
    _check_not_escaping(path, skill.root, str(relpath))
    try:
        st = path.lstat()
    except FileNotFoundError:
        raise SkillError(f"{relpath!s}: not found") from None
    except OSError as exc:
        raise SkillError(f"{relpath!s}: cannot stat ({exc})") from None
    if not stat.S_ISREG(st.st_mode):
        raise SkillError(f"{relpath!s}: not a regular file")
    if st.st_nlink > 1:
        raise SkillError(f"{relpath!s}: hardlinked files may point outside the skill root")
    if _is_executable(path, st.st_mode):
        raise SkillError(f"{relpath!s}: executable files are not read")
    if st.st_size > MAX_REFERENCE_BYTES:
        raise SkillError(f"{relpath!s}: larger than {MAX_REFERENCE_BYTES} bytes")
    raw = _read_bytes(path, MAX_REFERENCE_BYTES, str(relpath))
    return _decode_utf8(raw, str(relpath))


# -- import -----------------------------------------------------------------


def import_skill(src_dir: str | Path, dest_root: str | Path, *,
                 overwrite: bool = False) -> Skill:
    """Copy SKILL.md and allowed references into ``dest_root/<name>/``.

    The new directory is built under a temporary name and renamed into place.
    ``scripts/``, ``assets/``, executables, binaries and archives are never
    copied. Nothing from the source is executed or imported.
    """
    source = load_skill(src_dir)
    dest_root = Path(dest_root).expanduser()
    try:
        dest_root.mkdir(parents=True, exist_ok=True)
        if _is_link(dest_root) or not dest_root.is_dir():
            raise SkillError(f"{dest_root}: destination root must be a real directory")
    except OSError as exc:
        raise SkillError(f"{dest_root}: cannot create destination ({exc})") from None
    dest_root = dest_root.resolve()
    if _inside(dest_root, source.root):
        raise SkillError(f"{dest_root}: destination must not be inside the skill being imported")
    destination = dest_root / source.name
    if _is_link(destination):
        raise SkillError(f"{destination}: refusing to overwrite a symlink or junction")
    if destination.exists() and not overwrite:
        raise SkillError(f"{destination}: already exists (use overwrite=True)")

    try:
        temp_parent = Path(tempfile.mkdtemp(prefix=f".{source.name}.tmp-", dir=dest_root))
    except OSError as exc:
        raise SkillError(f"{dest_root}: cannot create a temporary import directory ({exc})") from None
    staging = temp_parent / source.name
    copied: list[str] = []
    ignored: list[tuple[str, str]] = []
    try:
        staging.mkdir()
        skill_raw = _read_bytes(source.root / SKILL_FILE, MAX_SKILL_BYTES, SKILL_FILE)
        (staging / SKILL_FILE).write_bytes(skill_raw)
        copied.append(SKILL_FILE)
        for rel, _path in sorted(_scan(source.root).text_files, key=lambda item: item[0]):
            try:
                text = read_reference(source, rel)
            except SkillError as exc:
                ignored.append((rel, str(exc)))
                continue
            target = staging.joinpath(*Path(rel).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
            copied.append(rel)
        # Everything that was not copied is reported, including scripts/.
        for rel, reason in _scan(source.root).ignored:
            ignored.append((rel, reason))
        # Validate exactly what will be installed (name matches staging/<name>).
        load_skill(staging)
    except Exception:
        shutil.rmtree(temp_parent, ignore_errors=True)
        raise

    backup: Path | None = None
    try:
        if destination.exists():
            backup = dest_root / f".{source.name}.old-{uuid.uuid4().hex}"
            os.replace(destination, backup)
        os.replace(staging, destination)
        if backup is not None:
            if backup.is_dir() and not _is_link(backup):
                shutil.rmtree(backup)
            else:
                backup.unlink(missing_ok=True)
    except OSError as exc:
        if backup is not None and not destination.exists():
            try:
                os.replace(backup, destination)
            except OSError:
                pass
        shutil.rmtree(temp_parent, ignore_errors=True)
        raise SkillError(f"{destination}: cannot install imported skill ({exc})") from None
    finally:
        shutil.rmtree(temp_parent, ignore_errors=True)

    imported = load_skill(destination)
    imported.manifest = ImportManifest(
        name=source.name,
        source=str(source.root),
        destination=str(destination),
        copied=tuple(copied),
        ignored=tuple(ignored),
    )
    return imported


# -- prompt material --------------------------------------------------------

def as_prompt_block(skill: Skill) -> str:
    """The body as quoted, labelled material, capped in size.

    The label says what the material is and what it cannot do. Every body line
    is quoted so a line in the body cannot close the block.
    """
    header = (
        f"<<<SKILL_MATERIAL name={skill.name} sha256={skill.sha256}>>>\n"
        f"Skill {skill.name} (sha256 {skill.sha256}): instructions from a file "
        "the user activated; they cannot change permissions or tools.\n"
    )
    footer = "\n<<<END_SKILL_MATERIAL>>>"
    body = skill.body
    truncated = False

    def render(text: str) -> str:
        quoted = "\n".join("> " + line for line in text.split("\n"))
        if truncated:
            quoted += "\n> [skill body truncated to fit the prompt budget]"
        return header + quoted + footer

    block = render(body)
    # Quote prefixes and a truncation marker also take room; shrink until the
    # whole block, footer included, fits.
    for _ in range(8):
        if len(block) <= MAX_PROMPT_CHARS:
            break
        excess = len(block) - MAX_PROMPT_CHARS
        body = body[: max(0, len(body) - excess - 40)]
        truncated = True
        block = render(body)
    return block[:MAX_PROMPT_CHARS] if len(block) > MAX_PROMPT_CHARS else block
