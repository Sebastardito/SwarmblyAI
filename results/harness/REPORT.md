# lce_validation — instrument and mock report

> **SIMULATION AND MOCK RUN — NOT EVIDENCE.** Instruments are simulations; experiments use `MockBackend`, which answers by rules and injects the effects being measured. These numbers show that each measurement responds to what it measures. No figure here may be cited as a result about language models or about the LCE.

Version 0.2.0.dev0 · seed 0

## Instruments

| instrument | hypothesis | prediction | passed |
|---|---|---|---|
| `error_agreement` | H-C17 (instrument: error agreement on MCQ) | independent ≈ chance ≈ 1/3; shared > chance; no change → CI inside ±0.10 in ≥80%; real change detected in ≥80% | yes |
| `anchor_gate` | anchoring rule (whitepaper 5.2; SPEC 6.3) | supported claims accepted (>=0.95); fabricated or misanchored claims rejected (acceptance <=0.05) | yes |
| `conformity` | H-C11 | conformist arm loses the minority (<5%); linear arm keeps its mean (~p0) | yes |
| `migration` | H-C8 (instrument only) | simulated F_ST decreases with Nm and tracks 1/(1+4Nm) within a factor of 2 in the band 0.5–2.25 | yes |
| `persistence` | H-C5 / H-C13 (instrument) | simulated loss matches q**r analytics; shared-operator placement is far worse | yes |
| `selection_bias` | H-C15 (instrument) | realised ≈ i·r·σ; selection-set estimate inflated; fresh-set estimate unbiased | yes |
| `collapse` | H-C7 / H-C12 (instrument) | replace erodes the tail; accumulate bounds it; anchored variation preserves or recovers it | yes |
| `r13_abstention` | el calificador separa abstención de contenido | 12/12 clasificaciones correctas en casos fabricados | yes |
| `r13_contradiction` | el calificador acepta vigente/desacuerdo y rechaza la versión antigua | >= 6/7 en casos fabricados | yes |
| `i1_equivalence` | el procedimiento detecta una fuga inyectada y no da falsas alarmas | >=95% de fugas detectadas y <=5% de falsas alarmas | yes |

## Mock experiments (plumbing only)

- Wiki on the fixture corpus: 13 claims, 5 trainable, anchor rejection rate 0.00.
- C1: accuracy with memory 0.90 vs without 0.00 (mock answers from context by rule).
- C2 / H-C2 lexicon adherence: 1.000 with Γ vs 0.033 without (difference 0.967, 95% CI [+0.917, +1.000]; 60 cells). Projection bytes 97.
- C2 / H-C17 homogeneity across users (mean cosine, 20 topics, T=0.7): baseline 0.855, projection 0.759, placebo 0.771. Reduction by projection +0.096 [+0.082, +0.110]; by placebo +0.084 [+0.075, +0.094]; projection beyond placebo +0.011 [+0.001, +0.022].
- C2 / H-C17 error agreement given both wrong (60 MCQ items): without Γ 0.569 (chance 0.341, excess [+0.075, +0.382]); with Γ 0.569; delta 0.000 [+0.000, +0.000]; invalid answers 0.000/0.000.
- C10 (simulated trainer): 5 accepted adapters over 6 generations, 6 distinct test sets.
- Canary: 8 items, 0 verified; training guard passed.
