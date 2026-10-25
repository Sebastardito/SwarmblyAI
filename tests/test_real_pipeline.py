"""End-to-end test of run_real and decide against a local fake OpenAI-compatible server.

The server answers with MockBackend, so this checks plumbing, guards and the
decision code, never model behaviour.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from swarmbly_lce.backends import MockBackend
from lce_validation import decide as D
from lce_validation import experiments as E
from lce_validation import mcq as M
from lce_validation import run_real


class _Handler(BaseHTTPRequestHandler):
    mocks: dict[str, MockBackend] = {}

    def log_message(self, *a):  # silence
        pass

    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.endswith("/api/version"):
            self._send({"version": "fake"})
        elif self.path.endswith("/api/tags"):
            self._send({"models": [{"name": m, "digest": "sha256:fake"} for m in self.mocks]})
        else:
            self.send_error(404)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.endswith("/chat/completions"):
            fam = req["model"].split(":")[0]
            mb = self.mocks.setdefault(req["model"], MockBackend(family=fam))
            text = mb.generate(req["messages"][0]["content"], temperature=req.get("temperature", 0), seed=req.get("seed", 0))
            self._send({"choices": [{"message": {"content": text}}]})
        elif self.path.endswith("/embeddings"):
            vecs = MockBackend().embed(req["input"])
            self._send({"data": [{"embedding": list(map(float, v))} for v in vecs]})
        else:
            self.send_error(404)


@pytest.fixture()
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()


def test_run_real_exploratory_end_to_end(server, tmp_path):
    rc = run_real.main(["--url", server, "--models", "fama:1b,famb:1b,famc:1b", "--embed-model", "emb",
                        "--mcq", str(E.FIXTURES / "mcq_synthetic.json"), "--out", str(tmp_path)])
    assert rc == 0
    res = json.loads((tmp_path / "results_real.json").read_text())
    assert res["header"]["backend_kind"] == "real"
    assert res["header"]["confirmatory"] is False          # no pre-registration given
    assert res["header"]["mcq_sha256"] == M.file_sha256(E.FIXTURES / "mcq_synthetic.json")
    assert "raw" in res["C2"] and res["C2"]["raw"]["mcq_without"]
    v = res["verdicts"]
    assert v["global_refusals"]
    assert all(r["verdict"] in {"exploratory_only", "refused", "not_tested"} for k, r in v.items() if isinstance(r, dict) and "verdict" in r)
    assert (tmp_path / "REPORT_REAL.md").read_text().startswith("# lce_validation — real-model run")


def test_run_real_refuses_missing_mcq(server, tmp_path):
    assert run_real.main(["--url", server, "--models", "fama:1b,famb:1b", "--mcq", str(tmp_path / "none.json"), "--out", str(tmp_path)]) == 2


def test_homogeneity_refuses_temperature_zero():
    fam = [MockBackend(family=f) for f in ("a", "b", "c")]
    with pytest.raises(ValueError):
        E.c2_projection(fam, MockBackend(), temperature=0.0, bootstrap_B=100)


def _res(**c2):
    base = {"header": {"confirmatory": True, "embed_model": "nomic-embed-text", "distinct_families": 3},
            "build_wiki": {"claims": 13}, "C1": {"acc_with_memory": 0.9, "acc_without_memory": 0.0, "gain": 0.9},
            "C2": {"projection_bytes_mean": 113, "nonempty_gamma_writes": 1.0, "nonempty_gamma_items": 1.0,
                   "lexicon": {"difference": 0.5, "difference_ci95": [0.3, 0.7]},
                   "homogeneity": {"reduction_projection": 0.05, "reduction_projection_ci95": [0.02, 0.08],
                                   "projection_beyond_placebo_ci95": [0.01, 0.03]},
                   "error_agreement": {"delta": 0.01, "delta_ci95": [-0.05, 0.07], "jointly_wrong_with": 500,
                                       "jointly_wrong_without": 500, "invalid_rate_with": 0.0, "invalid_rate_without": 0.0,
                                       "excess_ci95": [0.1, 0.2]}}}
    for k, v in c2.items():
        base["C2"][k].update(v)
    return base


def test_decide_rules():
    v = D.decide(_res())
    assert v["C1"]["verdict"] == "holds" and v["H-C2_lexicon"]["verdict"] == "holds"
    assert v["H-C17a"]["verdict"] == "holds" and v["H-C17b"]["verdict"] == "holds"
    assert v["H-C2_rho"]["verdict"] == "not_tested"
    v = D.decide(_res(error_agreement={"delta": 0.2, "delta_ci95": [0.12, 0.28]}))
    assert v["H-C17b"]["verdict"] == "falsified"
    v = D.decide(_res(error_agreement={"delta": 0.05, "delta_ci95": [-0.03, 0.13]}))
    assert v["H-C17b"]["verdict"] == "inconclusive"
    v = D.decide(_res(error_agreement={"jointly_wrong_with": 50}))
    assert v["H-C17b"]["verdict"] == "refused"
    v = D.decide(_res(homogeneity={"reduction_projection": -0.01, "reduction_projection_ci95": [-0.03, 0.01]}))
    assert v["H-C17a"]["verdict"] == "falsified"
    v = D.decide(_res(homogeneity={"projection_beyond_placebo_ci95": [-0.01, 0.02]}))
    assert "NOT shown" in v["H-C17a"]["qualification"]
    r = _res(); r["C2"]["projection_bytes_mean"] = 2       # run 1: empty projection
    v = D.decide(r)
    assert v["manipulation_check"]["passed"] is False
    assert all(v[k]["verdict"] == "refused" for k in ("H-C2_lexicon", "H-C17a", "H-C17b"))
    r = _res(); r["C2"]["nonempty_gamma_items"] = 0.5
    assert D.decide(r)["H-C17b"]["verdict"] == "refused"
    r = _res(); r["header"]["confirmatory"] = False
    assert D.decide(r)["H-C17a"]["verdict"] == "exploratory_only"


def test_mcq_parse_and_chance():
    assert M.parse_letter("B") == "B" and M.parse_letter("The answer is C.") == "C" and M.parse_letter("none") is None
    items = M.load_items(E.FIXTURES / "mcq_synthetic.json")
    assert len(items) == 60 and all(it.answer in "ABCD" for it in items)
    p = M.mcq_prompt(items[0], "register: formal")
    assert p.startswith(M.MCQ_MARKER) and "STYLE: register: formal" in p and "D. " in p


def test_canary_verify_rule(tmp_path):
    import csv
    from lce_validation import canary_verify as CV
    tpl = E.DATA / "canary_verification" / "plantilla_verificacion.csv"
    rows = list(csv.DictReader(open(tpl, encoding="utf-8")))
    k, m, o, g = "lo_conoce (si/no)", "significado_correcto (si/no/parcial)", "ofensivo_o_vulgar (si/no)", "glosa_corregida_es"
    sheets = []
    for name, fill in (("A", "si"), ("B", "si"), ("C", "no")):
        p = tmp_path / f"verificador_{name}.csv"
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            for r in rows:
                r2 = dict(r)
                r2[k] = fill
                r2[m] = "si" if fill == "si" else ""
                r2[o] = "si" if (name == "A" and r["termino"] == "chapa") else "no"
                if name == "B" and r["termino"] == "pite":
                    r2[m], r2[g] = "parcial", "un poco"
                w.writerow(r2)
        sheets.append(p)
    out, review = CV.merge(sheets, E.DATA / "canary_es-EC.json")
    v = {i["term"]: i for i in out["items"]}
    assert v["chuta"]["verified"] and v["chulla"]["verified"]          # current and candidate confirmed by 2 of 3
    assert "chapa" not in v                                             # candidate marked offensive: not added
    assert not v.get("pite", {"verified": False})["verified"]           # only 1 confirmation
    assert any(r["term"] == "pite" and r["corrections"] == ["un poco"] for r in review)
    with pytest.raises(ValueError):
        CV.merge(sheets[:2], E.DATA / "canary_es-EC.json")


def test_confirmatory_guard(tmp_path, monkeypatch):
    import subprocess
    def g(*a):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=tmp_path, check=True, capture_output=True)
    g("init", "-q")
    for d in ("docs", "lce_validation/data", "swarmbly_lce"):
        (tmp_path / d).mkdir(parents=True)
    pre = tmp_path / "docs" / "PRE.md"; pre.write_text("x")
    mcq = tmp_path / "lce_validation" / "data" / "m.json"; mcq.write_text("{}")
    (tmp_path / "swarmbly_lce" / "a.py").write_text("x")
    g("add", "-A"); g("commit", "-q", "-m", "init")
    monkeypatch.setattr(run_real, "ROOT", tmp_path)
    ok, problems = run_real._committed_and_clean([mcq, pre])
    assert ok, problems
    (tmp_path / "lce_validation" / "run_real.log").write_text("log")     # the run's own log does not count
    assert run_real._committed_and_clean([mcq, pre])[0]
    (tmp_path / "swarmbly_lce" / "a.py").write_text("changed")
    ok, problems = run_real._committed_and_clean([mcq, pre])
    assert not ok and any("uncommitted" in p for p in problems)
    new = tmp_path / "docs" / "NEW.md"; new.write_text("y")
    assert any("not committed" in p for p in run_real._committed_and_clean([new])[1])


def test_fetch_mcq_pages_and_resume(tmp_path, monkeypatch):
    from lce_validation import fetch_mcq as F
    N = 1234
    calls = []

    def fake_get(offset, length=1, retries=8):
        calls.append((offset, length))
        rows = [{"row": {"subject": "s", "question": f"q{i}", "choices": ["a", "b", "c", "d"], "answer": i % 4}}
                for i in range(offset, min(offset + length, N))]
        return {"num_rows_total": N, "rows": rows}

    monkeypatch.setattr(F, "_get", fake_get)
    monkeypatch.setattr(F, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    out = tmp_path / "m.json"
    assert F.main(["--n", "300", "--seed", "7", "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    idx = F.select_indices(N, 300, 7)
    assert [it["idx"] for it in data["items"]] == idx
    assert all(it["question"] == f"q{it['idx']}" and it["answer"] == "ABCD"[it["idx"] % 4] for it in data["items"])
    assert max(l for _, l in calls) <= F.PAGE and len(calls) <= 1 + N // F.PAGE + 1
    # Second run: refuses to overwrite; with the file removed, pages come from the cache.
    assert F.main(["--n", "300", "--seed", "7", "--out", str(out)]) == 1
    out.unlink(); n_before = len(calls)
    assert F.main(["--n", "300", "--seed", "7", "--out", str(out)]) == 0
    assert len(calls) == n_before + 1          # only the num_rows probe
    assert [it["idx"] for it in json.loads(out.read_text())["items"]] == idx


def test_quote_anchoring_and_span_projection():
    from swarmbly_lce.digest import locate_quote
    p = "Escribo en un registro técnico.\n\nPrefiero el término  inferencia descentralizada en lugar de computación distribuida."
    assert locate_quote(p, "Escribo en un registro técnico.") == (0, 31)
    s, e = locate_quote(p, "prefiero el término inferencia descentralizada")   # case and whitespace only
    assert p[s:e].startswith("Prefiero")
    assert locate_quote(p, "El usuario prefiere inferencia descentralizada") is None  # paraphrase is not a quote
    wiki, st = E.build_wiki(E.FIXTURES / "corpus", E.FIXTURES / "policy.json", MockBackend(), anchor_mode="quote")
    assert st["claims"] > 0 and st["anchor_verification"]["verified"] > 0 and st["claims_detail"]
    fams = [MockBackend(family=f) for f in ("a", "b", "c")]
    r = E.c2_projection(fams, MockBackend(), bootstrap_B=200, anchor_mode="quote", span_projection=True)
    assert r["nonempty_gamma_writes"] == 1.0 and r["projection_bytes_mean"] >= 20
    assert r["lexicon"]["cells"] > 0


def test_diagnose_runs(server, tmp_path):
    from lce_validation import diagnose
    assert diagnose.main(["--url", server, "--model", "fama:1b", "--out", str(tmp_path)]) == 0
    rep = json.loads((tmp_path / "diagnose_fama_1b.json").read_text())
    assert set(rep["corpora"]["u1"]) == {"offsets", "quote"}
    assert rep["corpora"]["u1"]["quote"]["projection_span_text"]["bytes"] >= 20


def test_reconcile_and_preflight(server, tmp_path, monkeypatch):
    from swarmbly_lce.claims import ClaimType
    from swarmbly_lce.digest import reconcile_type
    assert reconcile_type(ClaimType.USER_CLAIM, "Prefiero el término X en lugar de Y.") == ClaimType.PREFERENCE
    assert reconcile_type(ClaimType.FACT, "Escribo en un registro formal.") == ClaimType.STYLE
    assert reconcile_type(ClaimType.PROCEDURE, "Prefiero empezar por las figuras.") == ClaimType.PROCEDURE  # never from behavioral
    assert reconcile_type(ClaimType.USER_CLAIM, "El café mejora la concentración.") == ClaimType.USER_CLAIM
    # Preflight: with every projection forced empty, run_real stops before generating outcomes.
    from swarmbly_lce import projection as P
    monkeypatch.setattr(P.TaskProjection, "gamma_fields", lambda self: {})
    rc = run_real.main(["--url", server, "--models", "fama:1b,famb:1b,famc:1b", "--mcq", str(E.FIXTURES / "mcq_synthetic.json"),
                        "--out", str(tmp_path), "--preflight"])
    assert rc == 3
    res = json.loads((tmp_path / "results_real.json").read_text())
    assert res["C2"]["preflight_failed"] and "raw" not in res["C2"]
    assert res["verdicts"]["H-C17a"]["verdict"] in {"refused", "exploratory_only"}
