"""Recommended profile: plausible, explained, safe, reversible."""

from __future__ import annotations

from swarmbly_app.advisor import lce_levels, memory_budget, recommend

GB = 1024 ** 3


def hw(total_gb, *, unified=False, vram=None, free_gb=200, cores=8, battery=False):
    gpus = [{"name": "GPU", "vram": f"{vram * 1024} MiB"}] if vram else []
    return {
        "os": {"value": {"system": "Darwin" if unified else "Linux"}},
        "cpu": {"value": {"cores_physical": cores, "cores_logical": cores * 2}},
        "memory": {"value": {"total_bytes": total_gb * GB,
                             "available_bytes": total_gb * GB * 0.6}},
        "storage": {"value": {"free_bytes": free_gb * GB}},
        "gpu": {"value": {"gpus": gpus, "unified_memory": unified}},
        "power": {"value": {"has_battery": battery, "plugged": True}},
    }


def ollama(*models):
    return [{"name": "ollama", "available": True, "models": [
        {"name": n, "family": f, "size_bytes": int(gb * GB), "params_b": p,
         "kind": k} for n, f, gb, p, k in models]}]


LLAMA3B = ("llama3.2:3b", "llama", 2.0, 3.2, "chat")
QWEN3B = ("qwen2.5:3b", "qwen2", 1.9, 3.1, "chat")
LLAMA8B = ("llama3.1:8b", "llama", 4.9, 8.0, "chat")
NOMIC = ("nomic-embed-text:latest", "nomic-bert", 0.27, 0.137, "embedding")


class TestBudget:
    def test_apple_silicon_unified(self):
        b = memory_budget(hw(16, unified=True))
        assert b["kind"] == "unified" and 9 <= b["budget_gb"] <= 11

    def test_cpu_only(self):
        b = memory_budget(hw(8))
        assert b["kind"] == "ram" and b["budget_gb"] <= 5

    def test_nvidia_vram(self):
        assert memory_budget(hw(32, vram=8))["kind"] == "vram"

    def test_unknown_ram_is_unknown_not_invented(self):
        b = memory_budget({"memory": {"value": {}}})
        assert b["budget_gb"] is None and b["kind"] == "unknown"


class TestRecommend:
    def test_every_change_is_explained_and_safe(self):
        rec = recommend(hw(16, unified=True), ollama(LLAMA3B, QWEN3B, NOMIC))
        explained = {e["key"] for e in rec["explanations"]}
        for key in rec["changes"]:
            assert key in explained or key in ("swarm.hedge_fallback_ms",
                                               "model.local_models", "model.embed_model")
        # never turns on participation or network by itself
        assert "swarm.worker_enabled" not in rec["changes"]
        assert "swarm.lan_enabled" not in rec["changes"]
        assert "privacy.tier" not in rec["changes"]
        assert all(e["nature"] in ("measured", "estimated") for e in rec["explanations"])

    def test_multi_model_when_two_families_fit(self):
        rec = recommend(hw(16, unified=True), ollama(LLAMA3B, QWEN3B))
        assert rec["changes"]["model.multi_model"] is True
        assert set(rec["changes"]["model.local_models"]) == {"llama3.2:3b", "qwen2.5:3b"}

    def test_single_model_on_small_cpu_machine(self):
        rec = recommend(hw(8), ollama(LLAMA3B, QWEN3B))
        assert rec["changes"]["swarm.worker_max_concurrent"] == 1

    def test_embedder_server_only_when_installed(self):
        assert recommend(hw(16, unified=True), ollama(LLAMA3B, NOMIC))[
            "changes"]["model.embedder"] == "server"
        assert recommend(hw(16, unified=True), ollama(LLAMA3B))[
            "changes"]["model.embedder"] == "hash"

    def test_no_backend_warns_and_suggests_downloads_with_licence(self):
        rec = recommend(hw(16, unified=True), [{"name": "ollama", "available": False}])
        assert any("Ollama" in w for w in rec["warnings"])
        assert rec["downloads"]
        for d in rec["downloads"]:
            assert d["requires_consent"] and d["license"] and d["download_gb"] > 0

    def test_laptop_serves_only_plugged(self):
        rec = recommend(hw(16, unified=True, battery=True), ollama(LLAMA3B))
        assert rec["changes"]["swarm.worker_only_plugged"] is True


class TestLCE:
    def test_c4_never_recommended(self):
        for total in (8, 16, 64):
            levels = lce_levels(hw(total, unified=True),
                                memory_budget(hw(total, unified=True)), True)
            assert levels["recommended"] in ("C0", "C1")
            c4 = next(l for l in levels["levels"] if l["level"] == "C4")
            assert "experimental" in c4["status"]


class TestApplyRevert:
    def test_apply_then_revert(self, app_state):
        from fastapi.testclient import TestClient
        from swarmbly_app.api import create_app
        app = create_app(app_state)
        c = TestClient(app, base_url="http://127.0.0.1:8765")
        c.headers["X-Swarmbly-Token"] = app.state.guard.token
        before = c.get("/api/config").json()
        rec = c.get("/api/setup/recommendation").json()
        assert "explanations" in rec and "lce" in rec
        applied = c.post("/api/setup/apply", json={"keys": ["swarm.timeout_ms"]}).json()
        assert "swarm.timeout_ms" in applied["applied"]
        reverted = c.post("/api/setup/revert").json()
        assert reverted["swarm"]["timeout_ms"] == before["swarm"]["timeout_ms"]

    def test_permission_refusal_turns_lan_off(self, app_state):
        from fastapi.testclient import TestClient
        from swarmbly_app.api import create_app
        app = create_app(app_state)
        c = TestClient(app, base_url="http://127.0.0.1:8765")
        c.headers["X-Swarmbly-Token"] = app.state.guard.token
        app_state.config.update({"swarm.lan_enabled": True})
        perms = c.post("/api/permissions", json={"lan_discovery": False}).json()
        assert perms["lan_discovery"] is False
        assert app_state.config.get("swarm.lan_enabled") is False
