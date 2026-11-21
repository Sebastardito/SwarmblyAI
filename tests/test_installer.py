"""Installer helpers and the mirror check (run from the repository root: python -m pytest tests)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("install", ROOT / "installer" / "install.py")
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


def test_models_fit_the_memory():
    assert install.plan_models(32)[0][0] == "qwen2.5:7b"
    assert install.plan_models(16)[0][0] == "qwen2.5:3b"
    assert install.plan_models(6)[0][0] == "qwen2.5:1.5b"
    assert install.plan_models(16)[1][0] == "nomic-embed-text"
    assert len(install.plan_models(16, extra=True)) == 3


def test_app_dependencies_exclude_swarmbly_pins():
    deps = install._app_dependencies()
    assert deps and not any(d.lower().startswith("swarmbly") for d in deps)
    assert any(d.startswith("fastapi") for d in deps)


def test_the_sandbox_extra_comes_from_the_app_pyproject():
    deps = install._app_optional_dependencies("sandbox")
    assert any(d.startswith("wasi-python") for d in deps)
    assert any(d.startswith("wasmtime") for d in deps)


def test_both_languages_have_the_same_messages():
    assert set(install.T["es"]) == set(install.T["en"])


def test_available_memory_parsers_are_portable():
    meminfo = "MemTotal:       16000000 kB\nMemAvailable:    7000000 kB\n"
    assert install.parse_meminfo_available(meminfo) == 7.0
    assert install.parse_meminfo_available("MemTotal: 1 kB\n") is None

    vm_stat = (
        "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
        "Pages free:                          100000.\n"
        "Pages active:                        200000.\n"
        "Pages inactive:                      300000.\n"
        "Pages speculative:                    50000.\n")
    assert install.parse_vm_stat_available(vm_stat, 16384) == (450000 * 16384) / 1e9
    assert install.parse_vm_stat_available("Pages active: 1.\n", 4096) is None


def test_sandbox_decision_uses_available_memory_and_can_be_skipped():
    assert install.should_prepare_sandbox(8.0) == (True, "enough_memory")
    assert install.should_prepare_sandbox(6.0) == (True, "enough_memory")
    assert install.should_prepare_sandbox(5.9) == (False, "low_memory")
    assert install.should_prepare_sandbox(None) == (False, "unknown")
    assert install.should_prepare_sandbox(32.0, skip=True) == (False, "skip")


def test_a_failed_or_unknown_sandbox_option_is_left_to_first_launch():
    assert install.sandbox_prepare_status(0) == "done"
    assert install.sandbox_prepare_status(1) == "skipped"
    assert install.sandbox_prepare_status(2) == "skipped"
    assert install.sandbox_prepare_status(-1) == "skipped"


def test_dry_run_changes_nothing(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "installer" / "install.py"), "--quick", "--yes",
                          "--dry-run", "--lang", "en", "--venv", str(tmp_path / "venv"),
                          "--skip", "ollama,models,pdf,searxng,sandbox,shortcuts"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "[dry run]" in out.stdout and not (tmp_path / "venv").exists()


def test_mirrors_match_the_lock():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_components.py")],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout


def test_a_cp1252_console_does_not_crash(tmp_path):
    import os
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    out = subprocess.run([sys.executable, str(ROOT / "installer" / "install.py"), "--quick", "--yes",
                          "--dry-run", "--lang", "es", "--venv", str(tmp_path / "v"),
                          "--skip", "ollama,models,pdf,searxng,sandbox,shortcuts"],
                         capture_output=True, timeout=120, env=env)
    assert out.returncode == 0, out.stderr.decode("utf-8", "replace")


def test_on_macos_the_environment_goes_to_a_folder_icloud_does_not_sync(tmp_path):
    venv = tmp_path / ".venv"
    assert install.venv_target(venv, True) == tmp_path / ".venv.nosync"
    assert install.venv_target(venv, False) == venv
    (tmp_path / "custom").mkdir()
    assert install.venv_target(tmp_path / "custom", True) == tmp_path / "custom"


def test_python_minimum_is_311():
    assert install.MIN_PYTHON == (3, 11)
    assert install.python_supported((3, 11, 0))
    assert install.python_supported((3, 12, 4))
    assert not install.python_supported((3, 10, 14))
    assert not install.python_supported((3, 9, 19))


def test_main_refuses_python_310(monkeypatch, capsys):
    monkeypatch.setattr(install, "python_supported", lambda: False)
    assert install.main(["--quick", "--dry-run", "--lang", "en"]) == 1
    assert "3.11" in capsys.readouterr().out


def test_no_installer_or_doc_accepts_python_310():
    """The installer, both finders and the install guide must agree with the App."""
    for relative in ("installer/install.py", "install.sh", "install.ps1", "docs/INSTALL.md"):
        text = (ROOT / relative).read_text(encoding="utf-8-sig")
        assert "3.10" not in text, relative



def test_the_sandbox_step_never_fails_an_install_on_a_nonzero_exit(tmp_path, monkeypatch):
    class FakeUI:
        dry = False

        def __init__(self):
            self.results = []

        def __getitem__(self, key):
            return key

        def say(self, _text=""):
            pass

        def result(self, title, status, detail=""):
            self.results.append((status, detail))

    class Args:
        skip_prepare_sandbox = False

    class Ctx:
        args = Args()
        ui = FakeUI()
        app_entry = tmp_path / "swarmbly-app"

    ctx = Ctx()
    ctx.app_entry.write_text("", encoding="utf-8")
    monkeypatch.setattr(install, "available_memory_gb", lambda: 16.0)
    monkeypatch.setattr(install, "run", lambda *a, **k: subprocess.CompletedProcess(
        a[1] if len(a) > 1 else [], 2, "", "unknown option"))
    install.step_sandbox_prepare(ctx)
    assert ctx.ui.results == [("skipped", "sandbox_left")]
    assert "code 2" not in ctx.ui.results[0][1]  # the text template comes from T


def test_the_sandbox_step_can_be_skipped_by_flag(tmp_path, monkeypatch):
    class FakeUI:
        dry = False

        def __init__(self):
            self.results = []

        def __getitem__(self, key):
            return key

        def say(self, _text=""):
            pass

        def result(self, title, status, detail=""):
            self.results.append((status, detail))

    class Args:
        skip_prepare_sandbox = True

    class Ctx:
        args = Args()
        ui = FakeUI()
        app_entry = tmp_path / "swarmbly-app"

    ctx = Ctx()
    monkeypatch.setattr(install, "available_memory_gb", lambda: 16.0)
    install.step_sandbox_prepare(ctx)
    assert ctx.ui.results == [("skipped", "sandbox_skip")]
