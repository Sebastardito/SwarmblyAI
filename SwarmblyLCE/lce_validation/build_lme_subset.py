"""Construye el subconjunto LongMemEval (MIT) para la confirmatoria de R13.

Fuente: xiaowu0162/longmemeval (HuggingFace), licencia MIT, split
``longmemeval_s`` (500 preguntas). El subconjunto es 8 preguntas:
7 ``simple`` y 1 ``updated`` (Rachel: Chicago → «the suburbs», sesiones
32 y 46). Para cada pregunta se conserva la sesión RELEVANTE (la que
contiene la respuesta literal) y 2 sesiones distractoras (las dos primeras
que NO contienen la respuesta); la pregunta ``updated`` conserva además la
sesión con el valor anterior (régimen de actualización). Recorte declarado
en la Enmienda 8: el haystack completo (~50 sesiones por pregunta) no cabe
en el presupuesto de digestión local; el subconjunto queda congelado por
SHA-256 en ``lce_validation/data/lme_subset.json``.

Uso:
    python3 -m lce_validation.build_lme_subset /tmp/longmemeval_s.json
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = HERE / "fixtures" / "bench_users"

SELECT = {
    0: "simple",
    1: "simple",
    7: "simple",
    23: "simple",
    47: "simple",
    51: "simple",
    240: "simple",
    368: "updated",
}
# sesiones adicionales por pregunta (además de la relevante y los distractores)
EXTRA_SESSIONS = {368: [32]}   # la sesión con el valor anterior (Chicago)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower())


def main(argv: list[str] | None = None) -> int:
    src = Path(argv[0] if argv else sys.argv[1])
    data = json.loads(src.read_text(encoding="utf-8"))
    src_sha = hashlib.sha256(src.read_bytes()).hexdigest()

    base = FIX / "lme"
    conv = base / "teach" / "conversations"
    conv.mkdir(parents=True, exist_ok=True)
    policy = {"learning_policy": {"v": "0.1",
                                 "defaults": {"reference_only": True},
                                 "sources": {"teach/conversations": {
                                     "authored_by_user": True, "wiki": True}}}}
    (base / "policy.json").write_text(json.dumps(policy, ensure_ascii=False, indent=2),
                                      encoding="utf-8")

    questions = []
    used_ids: set[str] = set()
    meta = {"source": "xiaowu0162/longmemeval (HuggingFace), split longmemeval_s",
            "license": "MIT",
            "source_sha256": src_sha,
            "questions": []}
    for idx, qtype in sorted(SELECT.items()):
        x = data[idx]
        ans_norm = _norm(x["answer"])
        relevant = [j for j, s in enumerate(x["haystack_sessions"])
                    if ans_norm in _norm(" ".join(t["content"] for t in s))]
        if not relevant:
            raise SystemExit(f"pregunta {idx}: sin sesión relevante")
        keep = {relevant[0]}
        keep.update(EXTRA_SESSIONS.get(idx, []))
        dist = [j for j in range(len(x["haystack_sessions"])) if j not in keep
                and ans_norm not in _norm(" ".join(t["content"]
                                                   for t in x["haystack_sessions"][j]))]
        keep.update(dist[:2])
        sessions = []
        for j in sorted(keep):
            s = x["haystack_sessions"][j]
            sid = x["haystack_session_ids"][j]
            if sid in used_ids:           # ya escrita como doc de otra pregunta
                sessions.append(sid)
                continue
            used_ids.add(sid)
            safe = re.sub(r"[^a-zA-Z0-9_-]", "_", sid)[:80]
            lines = [f"# Conversación {sid}", ""]
            for t in s:
                role = "Usuario" if t["role"] == "user" else "Asistente"
                lines.append(f"**{role}:** {t['content']}")
                lines.append("")
            (conv / f"{safe}.md").write_text("\n".join(lines), encoding="utf-8")
            sessions.append(sid)
        questions.append({"q": x["question"], "gold": [x["answer"]], "type": qtype})
        meta["questions"].append({"index": idx, "lme_type": x["question_type"],
                                  "question": x["question"], "answer": x["answer"],
                                  "our_type": qtype,
                                  "sessions": sessions})
    (base / "questions_lme.json").write_text(
        json.dumps({"questions": questions}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    (HERE / "data" / "lme_subset.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"subconjunto LME: {len(questions)} preguntas, "
          f"{len(used_ids)} documentos de conversación")
    print("SHA fuente:", src_sha[:16])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
