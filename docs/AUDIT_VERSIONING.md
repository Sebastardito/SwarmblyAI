# Versioning audit — 27 August 2026

> ## Status update — the remedial steps have been carried out
>
> This is a dated audit and its findings are left as written. What has changed
> since, so that nobody works from a superseded instruction:
>
> - **F2 is resolved.** The work is committed. The history no longer stops
>   before V6, and the file list in F2 describes a working tree that no longer
>   exists.
> - **F4 and F6 step 1 are resolved.** The private set is listed explicitly in
>   `.gitignore` and removed from the index. **F6's `git` block has already been
>   run and must not be run again as written** — in particular its commit
>   message names only "V6 through tables-final", which is no longer what the
>   uncommitted work is. Compose a fresh message; keep step 2, the private-file
>   check, before any push.
> - **F5's remedy has been extended.** `run_metadata.json` carries
>   `code_sha256`, and two further reporting gates now exist that this audit
>   predates: below-floor rows are dropped from every figure by `publishable()`
>   rather than annotated, and a failed tier stamps a `FAILED` marker in its
>   own directory so that a result directory found later cannot be mistaken for
>   a completed run. When auditing a result directory, **check for `FAILED`
>   before reading anything in it.**
> - **Not resolved:** `results/` is still gitignored and still exists only on
>   one disk. The stale-copy and housekeeping steps below stand as written.

Prompted by a suspicion of drift after several bridge disconnections. The
suspicion was right about the symptom and wrong about the cause: **there is no
content drift.** What there is, is a repository whose history stops two weeks
before its working tree, two stale copies of the project on the same disk, a set
of private documents with nothing stopping them reaching a public remote, and
results that could not say what code produced them.

Method: hash every tracked path in both copies and compare, rather than reading
listings. The first attempt at this audit compared a hand-transcribed list and
reported eighteen false differences; that is recorded here because it is the same
class of error the audit was looking for.

---

## F1 — No content drift. The code is one version.

113 tracked paths compared by SHA-256.

| | |
|---|---|
| identical in both copies | **95** |
| **different** | **0** |
| absent from the working copy | 18 — all of them the private set, see F4 |

The working copy and this clone agree byte for byte everywhere they overlap. Any
fear that a bridge failure left half-written or divergent source files is
unfounded.

## F2 — The working copy's history stops before V6

```
working copy HEAD:  6e554ee  "Preflight: nine defects found before the run"
```

That commit predates the V6 run. Everything since exists **only as untracked or
modified files in the working tree**:

`swarmbly_v0/stats.py` · `tests/test_instrument.py` · `prompts/tables24.json` ·
`scripts/make_tables.py` · `scripts/reanalyse.py` · `scripts/rescore.py` ·
`docs/RESULTS_V6.md` · `docs/RESULTS_TABLES_DEV.md` ·
`docs/RESULTS_TABLES_DEV2.md` · `docs/RESULTS_TABLES_FINAL.md` ·
`docs/RUNBOOK.md` — plus the modifications to `metrics.py`, `experiment.py`,
`planner.py`, `grading.py`, `cli.py`, `composition_trace.py`,
`scripts/run_ollama.sh`, `scripts/make_complex.py` and four test files.

**Nothing since 25 August is committed anywhere durable.** `git log` in that
folder tells a story that ends before the metric correction, before Test 0,
before the corpus split, and before all three table runs. If the folder is lost,
so is the work; if a second machine clones the remote, it gets August code.

This is the actual versioning problem. It is not drift — it is the absence of a
record.

## F3 — Three copies of the project, two stale

| directory | HEAD | `metrics.py` | source files | results |
|---|---|---|---|---|
| **`Swarmbly-AI_Clean`** | `6e554ee` | **27 Aug** | 20 | 18 |
| `Swarmbly-AI` | `fbb2665` | 14 Aug | 15 | 5 |
| `Ori_Swarmbly-AI_Clean` | `453baf3` "Initial commit" | 14 Aug | 15 | 5 |

Only the first is live; nothing has written to the other two in two weeks. They
are not competing — but `Swarmbly-AI` carries the name the public repository
uses, and it still contains the private documents. A command run in the wrong
directory would push August code, or private documents, or both.

## F4 — The private documents had nothing protecting them

`.gitignore` in the working copy excluded exactly one private file,
`docs/AUDIT_V0.md`. It did **not** exclude:

`docs/DISCUSION_PUNTOS.*` · `docs/NAMING.*` · `docs/RESOLUCIONES.*` ·
`docs/Swarmbly_AI_Documento_Maestro_ES.*` ·
`docs/Swarmbly_AI_Master_Document_EN.*` · `publication/` (six documents,
including the disclosure and the submission draft)

and the working copy's remote is:

```
origin  https://github.com/Sebastardito/Swarmbly-AI.git  (push)
```

Those files are **absent** from that working tree, so nothing was at risk of
being committed by accident today. But nothing stopped them being re-added, and
**this clone still had all of them in its index** — so any patch, archive or pull
taken from it would have carried them.

**Fixed here:** removed from this clone's index, and listed explicitly in
`.gitignore` — one path per line rather than a wildcard, so that adding a new
private document is a deliberate act and the list reads as an inventory.

**Still to do on the working copy:** the same `.gitignore` change, in F6 below.

## F5 — No result could say what produced it

`run_metadata.json` recorded the corpus digest but nothing about the code.

| run | corpus | metric | how you could tell |
|---|---|---|---|
| `tables-dev-20260826-115300` | `47ceb5f0` *(not recorded)* | **defective** | directory timestamp |
| `tables-dev-20260827-095758` | `0c5cb7e2` | corrected | directory timestamp |
| `tables-final-20260827-102014` | `0c5cb7e2` | corrected | directory timestamp |

Three runs of the same tier, two scored by an arm-neutral metric and one by the
predecessor that inflated the fragmented arm, distinguishable only by a folder
name against a memory of when the fix landed. That is not evidence.

**Fixed:** `run_metadata.json` now carries `code_sha256` — a digest over the
package's sources — and `code_files`. Every future run is self-describing.
`tests/test_instrument.py` asserts the digest moves when any source byte moves.

`results/` is gitignored, correctly — the runs are large and reproducible from
code plus corpus. But that means the eighteen result directories exist **only**
on that disk, unversioned and unbacked.

## F6 — What to run, and why I am not running it

Git write commands through the device bridge leave a `.git/index.lock` the mount
cannot delete. Even `git status --untracked-files=all` writes the index. So the
commands below are for you to run; I have verified the state they act on.

```bash
cd ~/Desktop/Dev/P2PAI/Swarmbly-AI_Clean

# 1. Protect the private documents FIRST, before anything is staged.
#    Copy the .gitignore from this session's delivery, or append by hand:
cat >> .gitignore <<'EOF'
docs/AUDIT_V0.md
docs/DISCUSION_PUNTOS.*
docs/NAMING.*
docs/RESOLUCIONES.*
docs/Swarmbly_AI_Documento_Maestro_ES.*
docs/Swarmbly_AI_Master_Document_EN.*
publication/
_interno/
_to_delete/
_audit_*.txt
EOF

# 2. Confirm nothing private is about to be staged. Expect NO output.
git status --porcelain | grep -E 'DISCUSION|NAMING|RESOLUCIONES|Maestro|Master_Document|publication/|AUDIT_V0'

# 3. See what will be committed.
git status --short

# 4. Commit the two weeks of work.
git add -A
git commit -m "V6 through tables-final: instrument corrections, corpus split, results"

# 5. Push only when step 2 gave no output.
git push origin main
```

**Do not skip step 2.** It is the only check between a private document and a
public repository.

### The stale copies

```bash
cd ~/Desktop/Dev/P2PAI
mv Swarmbly-AI            _archive/Swarmbly-AI-stale-20260814
mv Ori_Swarmbly-AI_Clean  _archive/Ori_Swarmbly-AI_Clean-20260814
```

Renaming rather than deleting: they are the only copies of some August state, and
`_archive/` already exists. Once moved, `Swarmbly-AI_Clean` is the only directory
a command can land in by accident.

### Housekeeping

`_to_delete/` holds three scratch scripts I wrote to your disk during the metric
investigation. The bridge cannot delete; remove that folder yourself.
`_audit_cloud_manifest.txt` at the repo root is this audit's input and can go too.

---

## What the audit does **not** find

- No divergent or half-written source file.
- No result computed from a corpus other than the one its metadata names.
- No sign that a bridge failure corrupted anything. Every delivery either landed
  whole or failed loudly.

The disconnections cost time and forced re-delivery. They did not cost
correctness.
