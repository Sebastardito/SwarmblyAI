"""Draw the fixed MCQ item set for the error-agreement instrument (run ONCE, before any model call).

    python -m lce_validation.fetch_mcq                      # 1500 items, seed 20261005
    python -m lce_validation.fetch_mcq --n 1500 --seed 20261005 --out lce_validation/data/mmlu_test_1500.json

Source: MMLU (Hendrycks et al., 2021), Hugging Face dataset ``cais/mmlu``,
config ``all``, split ``test``; MIT licence. Items are drawn uniformly without
replacement with ``numpy.random.default_rng(seed)`` over the row indices
reported by the Hugging Face datasets-server, then fetched through its public
``/rows`` endpoint in pages of 100 rows, with backoff on rate limits and an
on-disk page cache (``~/.cache/swarmbly_lce/mmlu_pages``) so an interrupted
download resumes (standard library only, no ``datasets`` or ``pyarrow``).
How rows are downloaded does not affect which rows are selected. The script prints the SHA-256 of the file it writes;
``run_real`` records that hash in every result.

The pre-registration fixes the seed and the size. Re-drawing with another seed
after seeing results is a protocol deviation and must be declared.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

API = "https://datasets-server.huggingface.co/rows"
DATASET, CONFIG, SPLIT = "cais/mmlu", "all", "test"
DEFAULT_OUT = Path(__file__).resolve().parent / "data" / "mmlu_test_1500.json"


PAGE = 100  # maximum rows per request accepted by the datasets-server
CACHE = Path(os.environ.get("LCE_MCQ_CACHE", Path.home() / ".cache" / "swarmbly_lce" / "mmlu_pages"))


def _get(offset: int, length: int = 1, retries: int = 8) -> dict:
    """GET /rows with backoff. HTTP 429 honours Retry-After, otherwise waits 2, 4, 8 ... up to 60 s."""
    q = urllib.parse.urlencode({"dataset": DATASET, "config": CONFIG, "split": SPLIT, "offset": offset, "length": length})
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(f"{API}?{q}", timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            wait = min(60.0, 2.0 ** (attempt + 1))
            if exc.code == 429:
                try:
                    wait = max(wait, float(exc.headers.get("Retry-After", 0)))
                except (TypeError, ValueError):
                    pass
                print(f"  rate limited at offset {offset}; waiting {wait:.0f} s")
            time.sleep(wait)
        except Exception as exc:  # other network errors are retried, then raised
            last = exc
            time.sleep(min(60.0, 2.0 ** (attempt + 1)))
    raise RuntimeError(f"datasets-server unreachable at offset {offset}: {last}")


def _page(start: int, num_rows: int) -> list[dict]:
    """Rows [start, start+PAGE) of the split, cached on disk so an interrupted run resumes."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{CONFIG}_{SPLIT}_{start:06d}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    rows = [r["row"] for r in _get(start, min(PAGE, num_rows - start))["rows"]]
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    time.sleep(1.0)  # be polite to a public endpoint
    return rows


def select_indices(num_rows: int, n: int, seed: int) -> list[int]:
    rng = np.random.default_rng(seed)
    return sorted(int(i) for i in rng.choice(num_rows, size=n, replace=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=20261005)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        print(f"{out} already exists; the item set is drawn once. Delete it explicitly to re-draw (a declared deviation).")
        return 1
    first = _get(0)
    num_rows = int(first["num_rows_total"])
    idx = select_indices(num_rows, args.n, args.seed)
    # Fetch only the pages that contain selected rows, 100 rows per request, with
    # an on-disk cache. The selection itself depends only on (num_rows, n, seed).
    pages = sorted({(i // PAGE) * PAGE for i in idx})
    rows: dict[int, dict] = {}
    for k, start in enumerate(pages, 1):
        for j, row in enumerate(_page(start, num_rows)):
            rows[start + j] = row
        if k % 20 == 0 or k == len(pages):
            print(f"  pages {k}/{len(pages)}")
    items = []
    for i in idx:
        row = rows[i]
        items.append({"idx": i, "subject": row["subject"], "question": row["question"],
                      "choices": list(row["choices"]), "answer": "ABCD"[int(row["answer"])]})
    payload = {"source": f"huggingface.co/datasets/{DATASET}", "config": CONFIG, "split": SPLIT, "licence": "MIT",
               "citation": "Hendrycks, D., et al. (2021). Measuring massive multitask language understanding. ICLR 2021.",
               "num_rows_total": num_rows, "n": len(items), "seed": args.seed,
               "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "items": items}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(items)} items)\nsha256 {hashlib.sha256(out.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
