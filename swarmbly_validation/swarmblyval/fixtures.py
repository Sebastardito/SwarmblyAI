"""Golden fixtures: every number quoted in the source documents.

These are the *measurement record* reconstructed from the documents. They are
NOT new measurements — they are the documented data, transcribed so the harness
can (a) reproduce the documents' arithmetic and (b) apply the falsification
tests to the documented baseline. Where the documents do not provide a number
(e.g. per-prompt delta), the fixture is explicitly flagged as SYNTHETIC for
demonstration only, and the real value must be computed from the project corpus.
"""

# --- Coherence-tax measurement, 16 held-out prompts (WHITEPAPER_V2 §15.3) -----
TAX_16 = {
    "mean": 2.30,
    "ci_low": -2.05,
    "ci_high": 7.49,
    "median": 0.00,
    "n": 16,
    "n_at_or_below_zero": 11,       # 6 negative, 5 exactly zero
    "expensive": {                  # the two prompts that manufacture the mean
        "tbl24_outturn": 28.50,
        "tbl24_bonded": 23.08,
    },
    "mean_without_expensive": -1.06,
    "control_n8": {"mean": 16.23, "ci_low": 11.33, "ci_high": 20.28},
}

# --- Composition experiment (WHITEPAPER_V2 §15.5) -----------------------------
COMPOSITION = {
    "mean": -0.35,
    "sd_between": 20.36,     # between-cluster standard deviation
    "se": 4.16,              # measured standard error
    "ci_low": -8.49,
    "ci_high": 7.80,
    "threshold": 5.0,
    "n_implied": 24,         # (sd_between / se)^2 -> ~24 clusters
    "sample_min": 60,        # documented requirement
    "sample_margin": 72,
}

# --- Cardinality (M2, WHITEPAPER_V2 §11.3, §15.5) -----------------------------
UNIQUENESS = {
    "naive_contract": 6,     # asking term_once in the contract only
    "assembler_enforced": 18,  # mechanical enforcement at the assembler
    "monolithic": 13,
    "total": 24,
}

REPEAT = {                   # no_repeated_ngram — the irreducible class
    "fragmented": 4,
    "monolithic": 11,
    "total": 12,
}

# --- Confidence map withdrawals (WHITEPAPER_V2 §10.5.4, §15.3, L13) -----------
CONFIDENCE = {
    "r_peer_judge": -0.030,
    "units": 597,
    "judge_accept_rate": 0.933,
    "odds_ratios": (3.47, 0.26, 1.24),   # V3c: three mutually contradictory runs
}

# --- L-curve instrument verification (WHITEPAPER_V2 §15.4) --------------------
LCURVE = {
    "monolithic_global_ok": 1,   # 1 of 72
    "n_documents": 72,
    "local_lookup_ok": 0.84,     # 4 of 5 families do local lookups at ~0.84
    "families_doing_local": 4,
    "families_total": 5,
    "global_across_families_ok": 4,  # 4 of 60 across all families
    "global_across_families_n": 60,
    "ab_delta": 0.000,           # contract-wrapper A/B: 4/60 both ways
    "perfect_answer_score": 100.0,  # hand-built perfect answer scores 100% on all 72
}

# --- Triage incident (M3, WHITEPAPER_V2 §10.7) --------------------------------
TRIAGE_INCIDENT = {"contaminated": 42, "total": 60}

# --- Header-cost derivation (FUNDAMENTOS §0.B) --------------------------------
HEADER_FLOOR = [  # (prompt, |P|, N, measured floor, implied H)
    ("bulk_extraction_invoices", 160, 8, 2.86, 37),
    ("long_report_energy", 145, 8, 3.39, 43),
    ("code_shared_state_scheduler", 142, 8, 3.42, 43),
    ("creative_writing_lighthouse", 124, 8, 3.71, 42),
]

# --- Flank/rho table (FUNDAMENTOS §0.C) --------------------------------------
RHO_FROM_FLANK = [
    # (core C sentences, flank F sentences, % overlap, material/frag, rho)
    (50, 0,  0,  750,  1.05),
    (50, 10, 29, 1050, 1.45),
    (50, 17, 40, 1260, 1.73),
    (50, 25, 50, 1500, 2.05),
]

# --- Fragment sizes across corpora (FUNDAMENTOS §0.D) -------------------------
FRAGMENT_SIZES = [
    # (corpus, |P| tokens, sentences, material/fragment at N=3, at N=8)
    ("composition", 106,  6,   35,   13),
    ("v0",         143,  5,   48,   18),
    ("longform",   5855, 390, 1952, 732),
]

# --- Synthetic delta demonstration (NOT in the documents) ---------------------
# The 16-prompt tax measurement is documented as bimodal: 11 prompts at/below
# zero (low-delta), 2 expensive (high-delta), 3 residual small-positives.
# The documents do NOT publish per-prompt delta, so this fixture is a
# *demonstration* of the estimator and of the separation statistic. Real delta
# must be computed over the 16 prompts by tests/t4_delta.py::compute_delta().
SYNTHETIC_DELTA = {
    "low":  [0.10, 0.12, 0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30, 0.32, 0.35],  # 11 free
    "mid":  [0.48, 0.52, 0.55],                                                   # 3 residual
    "high": [0.82, 0.90],                                                          # 2 expensive
}
