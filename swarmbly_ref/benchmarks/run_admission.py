"""Admisión del corpus candidato `prompts/lcurve_v2.json` (T06).

La única comprobación que decide no es mecánica: ¿puede el pool responder las
preguntas globales con el brazo monolítico? Este runner mide la tasa global
sobre la mitad `dev` (la `final` no se toca — se evalúa una sola vez, después).

    python3 benchmarks/run_admission.py --models llama3.2:3b,phi3.5:3.8b

Escribe `data/admission.json` con la tasa por familia y por tipo de pregunta,
y ejecuta `corpus.preflight` con la tasa medida: admitido o rechazado, con la
razón. Nada se decide a mano.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)          # .../swarmbly_ref
ROOT = os.path.dirname(PKG)          # padre del paquete
sys.path.insert(0, ROOT)

from swarmbly_ref import llm  # noqa: E402


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def check_answer(q, answer_text):
    """Correcto si el valor esperado aparece en la respuesta (por id o en
    prosa): las familias no comparten formato y un parser por-id estricto
    penaliza formato, no capacidad."""
    if q.get("mode") == "numeric":
        try:
            exp = float(q["expected"])
        except (TypeError, ValueError):
            return False
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", answer_text)]
        return any(abs(x - exp) <= max(0.05, 0.02 * max(abs(x), exp))
                   for x in nums)
    return _norm(q.get("expected")) in _norm(answer_text)


def build_prompt(doc):
    lines = [
        "Read the material below. Answer EVERY question with ONE short "
        "factual answer, on its own line, prefixed by the question id. "
        "Answer format: \"NN: answer\".",
        "",
        "MATERIAL:",
        doc["material"],
        "",
        "QUESTIONS:",
    ]
    for q in doc["questions"]:
        lines.append(f"{q['id']}: {q['text']}")
    return "\n".join(lines)


def parse_answers(text):
    out = {}
    for line in text.splitlines():
        m = re.match(r"\s*(\d{1,2})\s*[:.)\-]\s*(.+)", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="llama3.2:3b,qwen2.5:3b,gemma2:2b,"
                                           "phi3.5:3.8b,granite3.1-dense:2b")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "admission.json"))
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    corpus_path = os.path.join(ROOT, "prompts", "lcurve_v2.json")
    d = json.load(open(corpus_path, encoding="utf-8"))
    dev_ids = d["_frozen"]["dev"]
    docs = [x for x in d["prompts"] if x["id"] in dev_ids]
    print(f"dev: {len(docs)} documentos, {len(models)} familias")

    report = {"corpus": "prompts/lcurve_v2.json", "dev": dev_ids,
              "families": {}}
    for model in models:
        glob_hits = glob_tot = loc_hits = loc_tot = 0
        per_doc = []
        for doc in docs:
            prompt = build_prompt(doc)
            n_ctx = max(4096, min(32768, len(doc["material"].split()) * 2 + 1024))
            out = llm.generate(model, prompt, max_tokens=220, num_ctx=n_ctx)
            answers = parse_answers(out["text"])
            gh = gt = lh = lt = 0
            for q in doc["questions"]:
                ans = answers.get(q["id"], out["text"])
                ok = check_answer(q, ans)
                if q["kind"] == "global":
                    gt += 1
                    gh += ok
                else:
                    lt += 1
                    lh += ok
            glob_hits += gh; glob_tot += gt
            loc_hits += lh; loc_tot += lt
            per_doc.append({"id": doc["id"], "global_ok": gh,
                            "global_n": gt, "local_ok": lh, "local_n": lt,
                            "response": out["text"][:2000]})
            print(f"  {model} {doc['id']}: global {gh}/{gt}, local {lh}/{lt}",
                  flush=True)
        rate = glob_hits / glob_tot if glob_tot else 0.0
        loc_rate = loc_hits / loc_tot if loc_tot else 0.0
        report["families"][model] = {
            "global_rate": round(rate, 4), "global": [glob_hits, glob_tot],
            "local_rate": round(loc_rate, 4), "local": [loc_hits, loc_tot],
            "per_doc": per_doc}
        print(f"  => {model}: global {rate:.1%} ({glob_hits}/{glob_tot}), "
              f"local {loc_rate:.1%}", flush=True)

    # compuerta de admisión con la tasa medida (el mínimo entre familias =
    # lo que el pool garantiza; se reporta también el máximo)
    rates = [v["global_rate"] for v in report["families"].values()]
    pool_min = min(rates) if rates else 0.0
    pool_max = max(rates) if rates else 0.0
    report["pool_global_rate_min"] = pool_min
    report["pool_global_rate_max"] = pool_max

    sys.path.insert(0, os.path.join(ROOT, "swarmbly_validation"))
    from swarmblyval import corpus as CO
    rep = CO.preflight(docs, monolithic_global_rate=pool_max)
    report["admission"] = {
        "admitted": rep.admitted,
        "report": str(rep),
        "floor": CO.MONOLITHIC_FLOOR,
        "rate_used": pool_max,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(report, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"reporte: {args.out}")
    print("\n=== compuerta de admisión ===")
    print(rep)
    print(f"ADMITIDO: {'SÍ' if rep.admitted else 'NO'} "
          f"(tasa global máxima {pool_max:.1%}, piso {CO.MONOLITHIC_FLOOR})")


if __name__ == "__main__":
    main()
