"""Declared constants and thresholds.

Every number here is quoted in the source documents. Where two documents
disagree, both values are kept and the discrepancy is surfaced in the report
rather than silently resolved — that is the project's own instrument
discipline (WHITEPAPER_V2_EN.md §9, §15.7: "a check that claims more than it
measured").
"""

# --- Semantic-unit fundamentals (WHITEPAPER_V2 §5, §6.5) ---------------------
S_TOKENS = 15.0          # tokens per sentence (median over the project corpus)
H_TOKENS = 39.0          # per-packet header cost (contract + glossary + format)
# FUNDAMENTOS §0.B despeja H implicita por prompt: 37, 43, 43, 42 (media 41.25).
# Kept separate so the report can flag the ~39 vs ~41 discrepancy.
H_IMPLIED_BY_PROMPT = (37.0, 43.0, 43.0, 42.0)

L_REF = 50               # reference fragment size, sentences (≈750 tok)
F_MEASURED = 10          # flank set by measurement (sentences)
F_ANALOGY = 25           # flank inherited by analogy (sentences; the 2.05 case)

# --- Abandonment criterion (WHITEPAPER_V2 §15.2) -----------------------------
CRITERION_TAX = 5.0      # % coherence degradation, judged on the CI UPPER bound
CI_LEVEL = 0.95          # 95% bootstrap interval, clustered by prompt
Z_95 = 1.96              # normal quantile for the sample-size arithmetic

# --- Instrument-discipline thresholds (WHITEPAPER_V2 §9, §15.7) ---------------
MIN_CLUSTERS = 20        # refuse a verdict below 20 prompt clusters
BASELINE_FLOOR = 0.20    # monolithic arm must clear this before comparison
FAMILY_LIST_MIN = 2      # refuse a model-family probe below two families
SE_CROSSCHECK_TOL = 0.25 # refuse if planned vs measured SE differ > 25%
MAX_POOLED_DROP_TOL = 1.0  # withdraw pooled conclusion if largest cell undoes it

# --- L-curve instrument (WHITEPAPER_V2 §15.4) --------------------------------
GLOBAL_QUESTION_FLOOR = 0.5   # monolithic arm must clear this ("say 0.5 or better")

# --- Coverage model (WHITEPAPER_V2 §7.4) -------------------------------------
LOSS_RATES = (0.05, 0.10, 0.20)
EPSILONS = (0.05, 0.01, 0.001)
