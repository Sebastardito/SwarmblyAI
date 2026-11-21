"""Hardware detection, model manager and inference adapter tests."""

from __future__ import annotations

import pytest

from swarmbly_app.hardware import detect_all, detect_cpu, detect_memory, detect_os
from swarmbly_app.inference.ollama import OllamaBackend
from swarmbly_app.inference.openai_compat import OpenAICompatBackend
from swarmbly_app.inference.registry import BackendRegistry, IncompleteSettings
from swarmbly_app.models import ModelManager, family_for


class TestHardware:
    def test_probes_report_source_and_confidence(self):
        report = detect_all()
        for name in ("os", "cpu", "memory", "storage", "gpu", "python_deps", "network"):
            assert name in report
            assert "source" in report[name]
            assert "confidence" in report[name]
            assert report[name]["confidence"] in ("measured", "estimated", "unknown")

    def test_no_invented_values(self):
        # Values may be unknown, but never silently assumed
        assert detect_os().confidence == "measured"
        assert detect_cpu().confidence in ("measured", "unknown")
        assert detect_memory().confidence in ("measured", "unknown")


class TestModelFamily:
    """One model must have one family with or without a running Ollama.

    Regression: on a developer machine Ollama reports ``llama``/``qwen2``
    from /api/tags, while CI without Ollama fell back to the tag
    (``llama3.2``/``qwen2.5``). Family-diverse consensus then grouped the
    same models differently, and two Llama versions could count as two
    families.
    """

    def test_backend_family_wins(self):
        assert family_for("llama3.2:3b", "llama") == "llama"

    def test_catalog_family_when_backend_is_silent(self):
        assert family_for("llama3.2:3b") == "llama"
        assert family_for("llama3.1:8b") == "llama"
        assert family_for("qwen2.5:3b") == "qwen2"

    def test_known_model_same_family_with_and_without_backend(self):
        for name in ("llama3.2:3b", "llama3.1:8b", "qwen2.5:3b",
                     "phi3.5:3.8b", "gemma2:2b"):
            assert family_for(name) == family_for(name, family_for(name))

    def test_unknown_model_falls_back_to_tag(self):
        assert family_for("custom-model:1b") == "custom-model"


class TestModelManager:
    def test_unreachable_ollama(self):
        mm = ModelManager(timeout=0.3)
        info = mm.probe_ollama("http://127.0.0.1:1")
        assert info.available is False
        assert info.name == "ollama"

    def test_recommendations_never_download(self):
        mm = ModelManager()
        recos = mm.recommend({"memory": {"value": {"total_bytes": 8 * 1024 ** 3}}})
        assert recos
        for reco in recos:
            assert reco["requires_authorization"] is True
            assert reco["install"].startswith("ollama pull")

    def test_first_available(self):
        from swarmbly_app.models import BackendInfo, DetectedModel
        info = BackendInfo(name="ollama", url="u", available=True,
                           models=[DetectedModel(name="m2", backend="ollama"),
                                   DetectedModel(name="m1", backend="ollama")])
        name, backend = ModelManager().first_available_model([info], preferred="m1")
        assert name == "m1" and backend is info


class TestInferenceAdapters:
    def test_ollama_unreachable(self):
        backend = OllamaBackend(url="http://127.0.0.1:1", timeout=0.3)
        assert backend.available() is False
        assert backend.list_models() == []

    def test_openai_compat_unreachable(self):
        backend = OpenAICompatBackend(base_url="http://127.0.0.1:1", timeout=0.3)
        assert backend.available() is False

    def test_registry_missing_url(self):
        registry = BackendRegistry()
        with pytest.raises(IncompleteSettings):
            registry.resolve({"model": {"backend": "openai_compat",
                                        "backend_url": ""}})

    def test_registry_ollama_fallback(self):
        registry = BackendRegistry()
        backend = registry.resolve({"model": {"backend": "ollama",
                                              "backend_url": "http://127.0.0.1:1"}})
        assert backend.name == "ollama"
