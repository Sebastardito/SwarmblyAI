"""Benchmark orchestration: monolithic vs fragmented arms over the corpus,
fault injection for the triage gate, k_epist multi-family runs for the
divergence map, and the L-curve sweep. Records append to a JSONL log with
resume-by-key so partial runs are safe."""

import json
import os
import re
import time

from . import assemble, grader, llm, packer, planner, triage, units

NUM_CTX_FRAG = 4096
NUM_CTX_MONO = 8192


def _record_path(data_dir):
    return os.path.join(data_dir, "benchmark.jsonl")


def _load_keys(path):
    keys = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        keys.add(json.loads(line).get("key"))
                    except json.JSONDecodeError:
                        pass
    return keys


def _append(path, record):
    with open(path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _words(text):
    """Palabras de la salida. Se registra como campo de primera clase porque el
    score sube con la longitud (T11): sin esto, el confundido sólo es visible
    re-derivándolo del texto, y una tabla agregada puede publicarse sin que
    nadie note que los brazos no escribieron lo mismo."""
    return len(str(text or "").split())


def _mono_words(data_dir, task_id, model):
    """Palabras del brazo monolítico de la MISMA celda, si ya está en el log.

    Devuelve ``None`` cuando el monolítico todavía no corrió: la razón de
    longitud queda sin medir en vez de rellenarse con un supuesto.
    """
    path = _record_path(data_dir)
    if not os.path.exists(path):
        return None
    want = f"{task_id}|mono|{model}"
    found = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or want not in line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("key") == want:
                found = r.get("output_words")
                if found is None:
                    found = _words(r.get("text"))
    return found


def _expected_items_for(task, fragment_text):
    """Mechanical triage items: entities mentioned in the assigned material."""
    return [e for e in task.get("entities", {})
            if re.search(re.escape(e), fragment_text, re.IGNORECASE)]


# ------------------------------------------------------------- arms --------

def run_monolithic(task, model, data_dir="data", max_retries=1):
    gamma = packer.build_gamma(task)
    prompt = (gamma + "\n\nSOURCE MATERIAL:\n" + task["material"]
              + "\n\n" + task["instruction_mono"])
    n_ctx = max(NUM_CTX_MONO, min(32768, units.approx_tokens(prompt) * 2 + 512))
    key = f"{task['id']}|mono|{model}"
    out = llm.generate(model, prompt, max_tokens=task["max_out_tokens"], num_ctx=n_ctx)
    g = grader.grade(task, out["text"])
    record = {
        "key": key, "task": task["id"], "arm": "mono", "model": model,
        "ts": time.time(),
        "prompt_tokens_approx": units.approx_tokens(prompt),
        "max_out_tokens": task["max_out_tokens"],
        "output_words": _words(out["text"]),
        "grade": g, "text": out["text"],
        "timing": {k: out[k] for k in
                   ("eval_count", "prompt_eval_count", "total_duration_s",
                    "load_duration_s")},
    }
    _append(_record_path(data_dir), record)
    return record


def run_fragmented(task, model, data_dir="data", L=None, F=None,
                   keep_alive="10m", cut_mode="weak",
                   match_output=False):
    """``match_output``: reparte el presupuesto de salida del monolítico entre
    los fragmentos en vez de dar a cada uno el presupuesto completo.

    Sin esto, un plan de N fragmentos recibe N veces los tokens de salida del
    brazo monolítico, y el score sube con la longitud (T11). El impuesto medido
    entonces no dice si fragmentar ayuda: dice que el brazo que escribe más
    puntúa más. Añadido el 25-09-2026."""
    L = L or task.get("L_target", 8)
    F = F if F is not None else task.get("F", 2)
    plan = planner.plan(task["material"], list(task.get("entities", {}).keys()),
                        L, F, task.get("unique_terms", []),
                        task.get("explicit_crossings", 0), cut_mode=cut_mode)
    if plan["n_fragments"] < 2:
        return {"key": None, "skip": "single fragment: nothing to assemble"}
    gamma = packer.build_gamma(task)
    budget = task["max_out_tokens"]
    if match_output:
        budget = max(60, task["max_out_tokens"] // max(1, plan["n_fragments"]))
    packets, results = [], []
    for i, (a, b) in enumerate(plan["ranges"]):
        frag = " ".join(plan["sentences"][a:b + 1])
        lead = " ".join(plan["sentences"][max(0, a - F):a]) if a > 0 else ""
        trail = " ".join(plan["sentences"][b + 1:b + 1 + F]) if b + 1 < len(plan["sentences"]) else ""
        instruction = task["instruction_frag"]
        packet = packer.build_packet(task, gamma, frag, lead, trail,
                                     plan["unique_here"][i], instruction, F)
        packets.append(packet)
        expected = _expected_items_for(task, frag)
        fraction = 1.0 if task["kind"] == "extraction" else 0.5
        out = llm.generate(model, packet, max_tokens=budget,
                           num_ctx=NUM_CTX_FRAG, keep_alive=keep_alive)
        verdict, reason = triage.check(out["text"], task, i, expected,
                                       required_fraction=fraction)
        attempts = 1
        if verdict != "PASS":
            # M3: isolate and retry, with the coverage made explicit
            p2 = (packet + "\n\nIMPORTANT: your answer MUST mention every "
                  "position or record given in your MATERIAL above.")
            out2 = llm.generate(model, p2, max_tokens=budget,
                                num_ctx=NUM_CTX_FRAG, keep_alive=keep_alive)
            verdict, reason = triage.check(out2["text"], task, i, expected,
                                           required_fraction=fraction)
            out = out2
            attempts = 2
        results.append({"text": out["text"], "verdict": verdict,
                        "reason": reason, "expected": expected,
                        "attempts": attempts,
                        "timing": {"eval_count": out["eval_count"],
                                   "total_duration_s": out["total_duration_s"],
                                   "load_duration_s": out["load_duration_s"]}})
    accepted = [r["text"] if r["verdict"] == "PASS" else "" for r in results]

    def bridge_fn(tail, head, gamma):
        p = (f"{gamma}\n\nWrite ONE transition sentence joining the end of this "
             f"text: '{tail[-200:]}' to the start of this text: '{head[:200]}'.")
        return llm.generate(model, p, max_tokens=60, num_ctx=NUM_CTX_FRAG)["text"]

    assembled = assemble.assemble(plan, accepted, gamma, task,
                                  embed=True, bridge_fn=bridge_fn)
    # M2 cerrado: si un término único quedó AUSENTE (sobre-compresión), se
    # re-despacha el fragmento DUEÑO (unique_here) con la mención explícita
    re_dispatched = []
    missing = list(assembled["cardinality"].get("enforced_missing", []))
    for term in missing:
        owner = next((i for i, terms in plan["unique_here"].items()
                      if term in terms), None)
        if owner is None:
            continue
        a, b = plan["ranges"][owner]
        frag = " ".join(plan["sentences"][a:b + 1])
        lead = " ".join(plan["sentences"][max(0, a - F):a]) if a > 0 else ""
        trail = " ".join(plan["sentences"][b + 1:b + 1 + F]) if b + 1 < len(plan["sentences"]) else ""
        p2 = packer.build_packet(
            task, gamma, frag, lead, trail, plan["unique_here"][owner],
            task["instruction_frag"] + f" IMPORTANT: your answer MUST contain "
            f"the term '{term}' exactly once.", F)
        out2 = llm.generate(model, p2, max_tokens=budget,
                            num_ctx=NUM_CTX_FRAG)
        accepted[owner] = out2["text"]
        re_dispatched.append({"term": term, "fragment": owner})
    if re_dispatched:
        assembled = assemble.assemble(plan, accepted, gamma, task,
                                      embed=True, bridge_fn=bridge_fn)
    # fallback mecánico final (M2, §18: imponer restricciones globales
    # mecánicamente): si un término sigue ausente, se añade la oración fuente
    # del material que lo contiene — información que el ensamblador posee
    still_missing = list(assembled["cardinality"].get("enforced_missing", []))
    if still_missing:
        extras = []
        for term in still_missing:
            for s in plan["sentences"]:
                if re.search(re.escape(term), s, re.IGNORECASE):
                    extras.append(s)
                    break
        if extras:
            accepted = list(accepted)
            accepted[-1] = (accepted[-1] + " " + " ".join(extras))
            assembled = assemble.assemble(plan, accepted, gamma, task,
                                          embed=True, bridge_fn=bridge_fn)
            re_dispatched.append({"term": still_missing,
                                  "fallback": "source sentence"})
    g = grader.grade(task, assembled["text"])
    material_tokens = units.approx_tokens(task["material"])
    rho, total_packet_tokens = packer.rho_total(packets, material_tokens)
    # el sufijo `|matched` mantiene las dos corridas en el mismo log: el resume
    # por key no debe confundir una celda con presupuesto igualado con la
    # original, porque son medidas distintas de la misma celda
    key = (f"{task['id']}|frag|{model}|L{L}F{F}"
           + (f"|{cut_mode}" if cut_mode != "weak" else "")
           + ("|matched" if match_output else ""))
    words = _words(assembled["text"])
    mono_words = _mono_words(data_dir, task["id"], model)
    record = {
        "key": key, "task": task["id"], "arm": "frag", "model": model,
        "L": L, "F": F, "ts": time.time(),
        "match_output": bool(match_output),
        "out_budget_per_fragment": budget,
        "out_budget_total": budget * plan["n_fragments"],
        "max_out_tokens": task["max_out_tokens"],
        "output_words": words,
        "length_ratio": (round(words / mono_words, 4)
                         if mono_words else None),
        "rho": rho, "rho_packet_tokens": total_packet_tokens,
        "material_tokens": material_tokens,
        "n_fragments": plan["n_fragments"], "delta": plan["delta"],
        "cuts": plan["cuts"], "unique_here": plan["unique_here"],
        "triage": [{"verdict": r["verdict"], "reason": r["reason"],
                    "attempts": r["attempts"]}
                   for r in results],
        "grade": g, "assembled_text": assembled["text"],
        "seams": assembled["seams"], "cardinality": assembled["cardinality"],
        "re_dispatched": re_dispatched,
        "per_packet_tokens": [units.approx_tokens(p) for p in packets],
        "per_packet_timing": [r["timing"] for r in results],
    }
    _append(_record_path(data_dir), record)
    return record


def run_fan_qa(task, model, data_dir="data"):
    """Fan topology: one micro-task per question, each packet carries the
    sentences that locate the answer (mechanical key lookup) plus flanks."""
    if task["id"] != "fan_qa":
        return {"skip": "not fan_qa"}
    gamma = packer.build_gamma(task)
    sentences = units.split_sentences(task["material"])
    results, packets = [], []
    for qi, (question, keys) in enumerate(task["questions"]):
        # locate the sentences containing the answer key (model-free)
        anchor = next((i for i, s in enumerate(sentences)
                       if any(k in s for k in keys)), len(sentences) // 2)
        lo = max(0, anchor - task.get("F", 1))
        hi = min(len(sentences), anchor + task.get("F", 1) + 1)
        frag = " ".join(sentences[lo:hi])
        packet = (gamma + f"\n\nMATERIAL:\n{frag}\n\n"
                  + task["instruction_frag"].format(question=question))
        packets.append(packet)
        out = llm.generate(model, packet, max_tokens=task["max_out_tokens"],
                           num_ctx=NUM_CTX_FRAG)
        verdict, reason = triage.check(out["text"], task, qi, None,
                                       min_tokens=1)
        results.append({"text": out["text"].strip(), "verdict": verdict,
                        "reason": reason})
    text = "\n".join(r["text"] for r in results if r["verdict"] == "PASS")
    g = grader.grade(task, text)
    rho, total = packer.rho_total(packets, units.approx_tokens(task["material"]))
    key = f"{task['id']}|frag|{model}|fan"
    record = {"key": key, "task": task["id"], "arm": "frag", "model": model,
              "topology": "fan", "ts": time.time(), "rho": rho,
              "n_fragments": len(task["questions"]),
              "grade": g, "assembled_text": text,
              "per_question": [{"q": task["questions"][i][0],
                                "answer": r["text"], "verdict": r["verdict"]}
                               for i, r in enumerate(results)]}
    _append(_record_path(data_dir), record)
    return record


def run_fault_injection(task, model, data_dir="data", L=4, corrupt=3):
    """The 42/60 incident, reproduced: some packets return another packet's
    answer. With the gate the contamination never reaches assembly; without
    it the blast radius spreads."""
    F = task.get("F", 1)
    plan = planner.plan(task["material"], list(task.get("entities", {}).keys()),
                        L, F, task.get("unique_terms", []),
                        task.get("explicit_crossings", 0))
    if plan["n_fragments"] < 4:
        return {"skip": f"need >=4 fragments, got {plan['n_fragments']}"}
    gamma = packer.build_gamma(task)
    results = []
    for i, (a, b) in enumerate(plan["ranges"]):
        frag = " ".join(plan["sentences"][a:b + 1])
        lead = " ".join(plan["sentences"][max(0, a - F):a]) if a > 0 else ""
        trail = " ".join(plan["sentences"][b + 1:b + 1 + F]) if b + 1 < len(plan["sentences"]) else ""
        packet = packer.build_packet(task, gamma, frag, lead, trail,
                                     plan["unique_here"][i],
                                     task["instruction_frag"], F)
        out = llm.generate(model, packet, max_tokens=task["max_out_tokens"],
                           num_ctx=NUM_CTX_FRAG)
        expected = _expected_items_for(task, frag)
        results.append({"text": out["text"], "expected": expected,
                        "verdict": triage.check(out["text"], task, i, expected)[0]})

    n = plan["n_fragments"]
    corrupted = list(results)
    for i in range(corrupt):
        src = (i + n // 2) % n
        corrupted[i] = dict(results[src])          # carries ANOTHER packet's answer
        corrupted[i]["expected"] = list(results[i]["expected"])  # but must answer task i

    # without gate: corrupted results enter assembly
    accepted_ungated = [r["text"] for r in corrupted]
    out_ungated = assemble.assemble(plan, accepted_ungated, gamma, task,
                                    embed=False, bridge_fn=None)
    g_ungated = grader.grade(task, out_ungated["text"])

    # with gate: the mechanical predicate rejects the contamination
    gated = []
    for i, r in enumerate(corrupted):
        verdict, reason = triage.check(r["text"], task, i, r["expected"])
        if verdict == "PASS":
            gated.append(r["text"])
        else:
            gated.append("")   # isolated; would be retried, never spliced
    out_gated = assemble.assemble(plan, gated, gamma, task,
                                  embed=False, bridge_fn=None)
    g_gated = grader.grade(task, out_gated["text"])

    rejected = sum(1 for i, r in enumerate(corrupted)
                   if triage.check(r["text"], task, i, r["expected"])[0] != "PASS")
    key = f"{task['id']}|fault|{model}|L{L}"
    record = {"key": key, "task": task["id"], "arm": "fault", "model": model,
              "L": L, "ts": time.time(), "n_fragments": n,
              "corrupted_packets": corrupt,
              "gate_rejected": rejected,
              "grade_ungated": g_ungated, "grade_gated": g_gated}
    _append(_record_path(data_dir), record)
    return record


def run_kepist(task, model_a, model_b, model_c, data_dir="data", L=8,
               fragment_index=0):
    """Epistemic redundancy: one fragment answered by three families, for the
    divergence-map alignment (M1)."""
    F = task.get("F", 2)
    plan = planner.plan(task["material"], list(task.get("entities", {}).keys()),
                        L, F, task.get("unique_terms", []),
                        task.get("explicit_crossings", 0))
    a, b = plan["ranges"][fragment_index]
    frag = " ".join(plan["sentences"][a:b + 1])
    lead = " ".join(plan["sentences"][max(0, a - F):a]) if a > 0 else ""
    trail = " ".join(plan["sentences"][b + 1:b + 1 + F]) if b + 1 < len(plan["sentences"]) else ""
    gamma = packer.build_gamma(task)
    packet = packer.build_packet(task, gamma, frag, lead, trail,
                                 plan["unique_here"][fragment_index],
                                 task["instruction_frag"], F)
    answers = {}
    for m in (model_a, model_b, model_c):
        out = llm.generate(m, packet, max_tokens=task["max_out_tokens"],
                           num_ctx=NUM_CTX_FRAG)
        answers[m] = out["text"]
    key = f"{task['id']}|kepist|{'+'.join(sorted([model_a, model_b, model_c]))}|L{L}"
    record = {"key": key, "task": task["id"], "arm": "kepist",
              "models": [model_a, model_b, model_c],
              "fragment": fragment_index, "material": frag, "ts": time.time(),
              "answers": answers}
    _append(_record_path(data_dir), record)
    return record


def run_selfconsistency(task, model, data_dir="data", k=5, temperature=0.7):
    """The v0.3 mandatory baseline: a SINGLE agent with self-consistency.

    k stochastic samples (temperature>0) of the monolithic prompt; the
    consensus answer is the semantic medoid (sample with highest mean
    embedding similarity to the others — the SelfCheckGPT-style selection).
    Recorded so the fragmented arm can be judged against this rival, not
    only against single-pass monolithic generation (Zhang et al.).
    """
    gamma = packer.build_gamma(task)
    prompt = (gamma + "\n\nSOURCE MATERIAL:\n" + task["material"]
              + "\n\n" + task["instruction_mono"])
    n_ctx = max(NUM_CTX_MONO, min(32768, units.approx_tokens(prompt) * 2 + 512))
    samples = []
    for i in range(k):
        out = llm.generate(model, prompt, max_tokens=task["max_out_tokens"],
                           temperature=temperature, seed=i, num_ctx=n_ctx)
        samples.append({"text": out["text"], "seed": i,
                        "eval_count": out["eval_count"],
                        "total_duration_s": out["total_duration_s"]})
    texts = [s["text"] for s in samples]
    embs = llm.embed(texts)
    sim = [[llm.cosine(a, b) for b in embs] for a in embs]
    medoid = max(range(k), key=lambda i: sum(sim[i]))
    g = grader.grade(task, texts[medoid])
    key = f"{task['id']}|selfcons|{model}|k{k}"
    record = {"key": key, "task": task["id"], "arm": "selfcons", "model": model,
              "k": k, "temperature": temperature, "ts": time.time(),
              "grade": g, "text": texts[medoid], "medoid_index": medoid,
              "samples": [s["text"] for s in samples],
              "medoid_sim_mean": round(sum(sim[medoid]) / k, 3)}
    _append(_record_path(data_dir), record)
    return record




def run_probe(task, model, data_dir="data", n_rows=4, seed=7):
    """Sonda de capacidad PRE-DISPATCH: ¿puede el nodo sumar n valores?

    Feature candidate del router (routability): el orquestador mide barato,
    antes de despachar, si el nodo sabe agregar — el predictor del fallo
    monolítico que las features estáticas no capturan.
    """
    import random
    rng = random.Random(seed)
    rows = [r for r in task.get("numeric_keys", [])]
    rng.shuffle(rows)
    sample = rows[:n_rows]
    target = round(sum(float(x) for x in sample), 1)
    prompt = ("What is the sum of these values? Answer with ONLY the number.\n"
              + " ".join(sample))
    out = llm.generate(model, prompt, max_tokens=20, num_ctx=1024)
    text = out["text"]
    import re
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)]
    correct = any(abs(x - target) <= max(0.05, 0.02 * max(abs(x), target))
                  for x in nums)
    key = f"{task['id']}|probe|{model}"
    record = {"key": key, "task": task["id"], "arm": "probe", "model": model,
              "target": target, "sample": sample, "correct": correct,
              "answer": text[:120], "ts": time.time()}
    _append(_record_path(data_dir), record)
    return record



def run_probe2(model, kind, data_dir="data"):
    """Sonda de capacidad genérica (extracción / formato), independiente de
    tarea: mide habilidades del nodo ANTES de cualquier despacho."""
    import re as _re
    if kind == "extract":
        prompt = ("Extract the value from this sentence and answer with ONLY "
                  "the number: 'Shipment SH-2001 travels from Meridian to "
                  "Harborline with a declared weight of 13.7 tonnes.'")
        out = llm.generate(model, prompt, max_tokens=20, num_ctx=1024)
        nums = [float(x) for x in _re.findall(r"\d+(?:\.\d+)?", out["text"])]
        correct = any(abs(x - 13.7) <= max(0.05, 0.02 * 13.7) for x in nums)
        answer = out["text"][:120]
    elif kind == "format":
        prompt = ("Return a JSON object with fields 'name' and 'units' for: "
                  "'The Planta Uno facility produced 5200 units.'")
        out = llm.generate(model, prompt, max_tokens=60, num_ctx=1024)
        try:
            obj = json.loads(out["text"])
            correct = isinstance(obj, dict) and "name" in obj and "units" in obj
        except json.JSONDecodeError:
            correct = False
        answer = out["text"][:120]
    else:
        return {"skip": f"kind desconocido {kind}"}
    key = f"probe2|{kind}|{model}"
    record = {"key": key, "arm": "probe2", "kind": kind, "model": model,
              "correct": correct, "answer": answer, "ts": time.time()}
    _append(_record_path(data_dir), record)
    return record

def run_router_check(task):
    """Router decision against corpus truth (no LLM call needed)."""
    decide, reason = planner.router(task, task["material"])
    return {"task": task["id"], "decided": decide, "reason": reason,
            "truth": bool(task.get("decomposable")),
            "correct": decide == bool(task.get("decomposable"))}
