"""The package is local by construction, and the metadata says so.

The import test parses the package rather than trusting a review: an import of
the App, the LCE or ``swarmbly_v0`` would couple the runtime to the thing it is
supposed to be driven by, and a network or subprocess import would create an
egress path outside the injected policy.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "swarmbly_agent"

FORBIDDEN_ROOTS = {
    "swarmbly_app",
    "swarmbly_lce",
    "swarmbly_v0",
    # network
    "http",
    "httpx",
    "requests",
    "socket",
    "ssl",
    "urllib",
    "websockets",
    # processes
    "subprocess",
    "multiprocessing",
}

FORBIDDEN_CALLS = {
    "system",
    "popen",
    "Popen",
    "urlopen",
    "create_connection",
    "check_output",
    "check_call",
}


def _files() -> list[Path]:
    return sorted(PACKAGE.glob("*.py"))


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


@pytest.mark.parametrize("path", _files(), ids=lambda path: path.name)
def test_no_forbidden_imports(path: Path) -> None:
    roots = _imported_roots(ast.parse(path.read_text(encoding="utf-8")))
    assert not roots & FORBIDDEN_ROOTS, (
        f"{path.name} imports {sorted(roots & FORBIDDEN_ROOTS)}. The runtime is "
        "local: the App supplies the model and the tool broker, and no package "
        "here may open a network connection or start a process."
    )


@pytest.mark.parametrize("path", _files(), ids=lambda path: path.name)
def test_no_process_or_network_calls(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = sorted(
        {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in FORBIDDEN_CALLS
        }
    )
    assert not offenders, f"{path.name} calls {offenders}; policy is injected, not implemented here."


def test_the_package_is_dependency_free() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    metadata = project["project"]
    assert metadata["name"] == "swarmbly-agent"
    assert metadata["version"] == "0.1.0"
    assert metadata["requires-python"] == ">=3.11"
    assert metadata["dependencies"] == []
    assert metadata["license"]["text"] == "AGPL-3.0-or-later"
    assert metadata["authors"] == [{"name": "Sebastián A. Espinoza-Ulloa"}]


def test_the_expected_layout_exists() -> None:
    assert (ROOT / "pyproject.toml").is_file()
    assert (ROOT / "README.md").is_file()
    assert (ROOT / "tests").is_dir()
    assert (PACKAGE / "__init__.py").is_file()
    assert (PACKAGE / "types.py").is_file()
    assert (PACKAGE / "runtime.py").is_file()
    assert (PACKAGE / "parse.py").is_file()


def test_the_public_names_are_exported() -> None:
    import swarmbly_agent

    for name in (
        "AgentRuntime",
        "Budget",
        "Final",
        "ToolRequest",
        "Observation",
        "RunState",
        "Step",
        "ToolDescriptor",
        "Allow",
        "Deny",
        "NeedsApproval",
        "parse_json_action",
    ):
        assert hasattr(swarmbly_agent, name), f"missing public name: {name}"
