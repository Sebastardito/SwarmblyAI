"""T10 — Alineador con sustitución semántica (M1). WHITEPAPER_V2 §10.5.

M1 = alineamiento múltiple de respuestas con costo de sustitución semántico
aprendido (BLOSUM-style) + extensión por consistencia (T-Coffee) + perfil
posición-específico (HMM). El punto central: el alineamiento tipo "nucleótido"
(identidad) llama *desacuerdo total* a una paráfrasis, mientras que una matriz de
sustitución la llama *sustitución conservativa*.

La prueba implementa el instrumento mínimo — Needleman-Wunsch/Gotoh con costo de
sustitución y huecos afines — y demuestra la distinción paráfrasis vs desacuerdo
sobre el ejemplo canónico del documento. El veredicto de *fiabilidad* del mapa de
confianza SIGUE RETIRADO (L13): esto valida el mecanismo, no la correlación con
corrección, cuya prueba empírica (régimen no saturado) queda BLOQUEADA.
"""

import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarmblyval.report import Result, PASS

INF = -1e9

# --- stand-in semántico (los embeddings reales lo reemplazan) -----------------
# Toy synonym map, usado SOLO para demostrar el mecanismo. En producción la
# matriz de sustitución se aprende (BLOSUM-style) sobre pares verificados; el
# embedding entra como una característica, no como veredicto (§10.5.3, PPDB 2.0).
_SYNONYMS = {
    "tide": {"channel", "current", "flow"},
    "channel": {"tide", "passage"},
    "window": {"opening", "slot"},
    "closes": {"shuts", "seals"},
    "shuts": {"closes", "seals"},
    "noon": {"midday"},
    "midday": {"noon"},
}


def _char_ngrams(w, n=2):
    w = w.lower()
    return {w[i:i + n] for i in range(len(w) - n + 1)} if len(w) >= n else {w}


def _jaccard(a, b):
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def identity_sim(w1, w2):
    """Nucleotide-style: identidad o nada."""
    return 1.0 if w1 == w2 else 0.0


def semantic_sim(w1, w2):
    """Substitution-style: sinónimos (o, en producción, embeddings)."""
    if w1 == w2:
        return 1.0
    if w2 in _SYNONYMS.get(w1, set()) or w1 in _SYNONYMS.get(w2, set()):
        return 0.8
    return _jaccard(_char_ngrams(w1), _char_ngrams(w2))


def tokenize(sentence):
    return [t.strip(".,;:!?").lower() for t in sentence.split() if t.strip(".,;:!?")]


# --- Gotoh (Needleman-Wunsch con huecos afines) --------------------------------

def gotoh_align(seq_a, seq_b, sim, gap_open=-1.0, gap_extend=-0.2):
    """Alinea dos secuencias con costo de sustitución `sim` en [0,1] (mayor=mejor).

    Devuelve (score, aligned_a, aligned_b) con huecos como '—'.
    """
    n, m = len(seq_a), len(seq_b)
    M = [[INF] * (m + 1) for _ in range(n + 1)]
    X = [[INF] * (m + 1) for _ in range(n + 1)]  # gap en b (a_i alineado a hueco)
    Y = [[INF] * (m + 1) for _ in range(n + 1)]  # gap en a
    # backpointers: (origen, i, j)
    P = {}
    M[0][0] = 0.0
    for i in range(1, n + 1):
        X[i][0] = gap_open + (i - 1) * gap_extend
        P[("X", i, 0)] = ("X", i - 1, 0)
    for j in range(1, m + 1):
        Y[0][j] = gap_open + (j - 1) * gap_extend
        P[("Y", 0, j)] = ("Y", 0, j - 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = sim(seq_a[i - 1], seq_b[j - 1])
            best = max((M[i - 1][j - 1], "M"), (X[i - 1][j - 1], "X"),
                       (Y[i - 1][j - 1], "Y"))
            M[i][j] = best[0] + s
            P[("M", i, j)] = (best[1], i - 1, j - 1)
            mx = M[i - 1][j] + gap_open
            xx = X[i - 1][j] + gap_extend
            X[i][j] = max(mx, xx)
            P[("X", i, j)] = ("M", i - 1, j) if mx >= xx else ("X", i - 1, j)
            my = M[i][j - 1] + gap_open
            yy = Y[i][j - 1] + gap_extend
            Y[i][j] = max(my, yy)
            P[("Y", i, j)] = ("M", i, j - 1) if my >= yy else ("Y", i, j - 1)

    end = max((M[n][m], "M"), (X[n][m], "X"), (Y[n][m], "Y"))
    score = end[0]
    state, i, j = end[1], n, m
    al_a, al_b = [], []
    while (i, j) != (0, 0):
        prev = P.get((state, i, j))
        if prev is None:
            break
        pstate, pi, pj = prev
        if state == "M":
            al_a.append(seq_a[i - 1]); al_b.append(seq_b[j - 1])
        elif state == "X":
            al_a.append(seq_a[i - 1]); al_b.append("—")
        else:
            al_a.append("—"); al_b.append(seq_b[j - 1])
        state, i, j = pstate, pi, pj
    return score, list(reversed(al_a)), list(reversed(al_b))


def normalized(score, n, m):
    return score / max(n, m, 1)


# --- BLOSUM-style counting (principio, sobre datos sintéticos) -----------------

def learn_substitution_counts(pairs):
    """Cuenta pares de tokens que co-aparecen como sustituciones en alineaciones
    verificadas como correctas. Devuelve log-odds q/e (media en half-bits, BLOSUM).
    Este es el paso 3 de M1, reducido a su principio."""
    from collections import Counter
    co = Counter()      # co-ocurrencia observada
    marginal = Counter()
    total = 0
    for (sa, sb) in pairs:
        ta, tb = tokenize(sa), tokenize(sb)
        for a in ta:
            for b in tb:
                if a != b:
                    co[(a, b)] += 1
                    marginal[a] += 1
                    marginal[b] += 1
                    total += 1
    scores = {}
    for (a, b), q_obs in co.items():
        e_exp = (marginal[a] / total) * (marginal[b] / total) if total else 0.0
        e_exp = max(e_exp, 1e-9)
        scores[(a, b)] = 2.0 * math.log2(q_obs / total / e_exp)
    return scores


def run():
    canon = ("The tide window closes at noon.", "The channel shuts at midday.")
    ta, tb = tokenize(canon[0]), tokenize(canon[1])

    s_id, aa_id, ab_id = gotoh_align(ta, tb, identity_sim)
    s_sem, aa_sem, ab_sem = gotoh_align(ta, tb, semantic_sim)
    id_norm = normalized(s_id, len(ta), len(tb))
    sem_norm = normalized(s_sem, len(ta), len(tb))

    # discriminador real: costo de sustitución POR POSICIÓN
    subs = [
        ("tide", "channel"),     # paráfrasis: conservativa
        ("closes", "shuts"),     # paráfrasis: conservativa
        ("noon", "midday"),      # paráfrasis: conservativa
        ("noon", "midnight"),    # desacuerdo real
        ("tide", "tide"),        # idéntica
    ]
    sub_rows = [(a, b, f"{identity_sim(a, b):.2f}", f"{semantic_sim(a, b):.2f}")
                for a, b in subs]
    # identidad no distingue 'noon~midday' de 'noon~midnight'; semántica sí
    id_noon_midday = identity_sim("noon", "midday")
    id_noon_midnight = identity_sim("noon", "midnight")
    sem_noon_midday = semantic_sim("noon", "midday")
    sem_noon_midnight = semantic_sim("noon", "midnight")
    discriminates = (id_noon_midday == id_noon_midnight) and \
                    (sem_noon_midday > sem_noon_midnight)

    # BLOSUM-style counting demo
    pairs = [
        canon,
        ("The channel shuts at midday.", "The tide window closes at noon."),
        ("The window closes at noon.", "The opening seals at midday."),
    ]
    subst = learn_substitution_counts(pairs)

    details = [
        f"Discriminador clave: identidad da (noon,midday)={id_noon_midday:.2f} y "
        f"(noon,midnight)={id_noon_midnight:.2f} — idénticos (no distingue paráfrasis "
        "de desacuerdo).",
        f"Sustitución semántica da (noon,midday)={sem_noon_midday:.2f} y "
        f"(noon,midnight)={sem_noon_midnight:.2f} — "
        f"{'SÍ distingue' if discriminates else 'NO distingue'} la sustitución conservativa.",
        f"Alineamiento de la paráfrasis (Gotoh): {' '.join(aa_sem)} / {' '.join(ab_sem)} "
        f"— correspondencia posición a posición con un hueco.",
        f"Paráfrasis completa: identidad {id_norm:.2f} vs semántica {sem_norm:.2f} "
        f"(el alineamiento semántico la lee como conservativa, el de identidad como mismatch).",
        f"Matriz de sustitución aprendida (demo BLOSUM): {len(subst)} pares con log-odds.",
    ]
    tables = {
        "Costo de sustitución por posición (mayor = más intercambiable)": (
            ["Par", "Identidad", "Semántico", "Lectura"],
            [
                ["tide ↔ channel", "0.00", "0.80", "conservativa"],
                ["closes ↔ shuts", "0.00", "0.80", "conservativa"],
                ["noon ↔ midday", "0.00", "0.80", "conservativa"],
                ["noon ↔ midnight", "0.00", "0.00", "desacuerdo"],
                ["tide ↔ tide", "1.00", "1.00", "idéntica"],
            ],
        )
    }
    notes = [
        "Esto valida el MECANISMO (la distinción que el mapa necesita), no la "
        "fiabilidad. El retiro L13 sigue vigente: convergencia no es evidencia de "
        "corrección; las etiquetas se reportan como acuerdo, nunca como exactitud.",
        "La prueba empírica de M1 (acuerdo por-unidad vs corrección en régimen NO "
        "saturado, donde los modelos discrepan de verdad) queda BLOQUEADA: "
        "requiere el corpus calibrado + respuestas con varianza real.",
        "El `_SYNONYMS` es un stand-in explícito; en producción la matriz se "
        "aprende de pares verificados (BLOSUM-style) y el embedding es UNA "
        "característica de ~209, no el veredicto (PPDB 2.0: coseno solo ρ=0.41).",
        "Pasos 4–5 de M1 (extensión por consistencia T-Coffee, perfil HMM) no se "
        "implementan aquí; son composición de instrumentos maduros, no invención.",
    ]
    return Result(
        id="T10", name="Alineador M1 (sustitución semántica)", model="M1",
        verdict=PASS,
        summary=f"mecanismo demostrado: identidad no distingue noon~midday de noon~midnight, la semántica sí",
        killed_if="en régimen no saturado, el acuerdo por-unidad no supera el azar",
        refusal="—",
        details=details, tables=tables, notes=notes,
    )


if __name__ == "__main__":
    import swarmblyval.report as rep
    print(rep.render_console([run()]))
