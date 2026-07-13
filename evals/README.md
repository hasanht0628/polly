# Eval sets

Suites under `evals/court/`, `evals/classification/`, and `evals/portfolio/`.

## Court calendar (`evals/court/`)

Three fixture PDFs, three eval stages:

| Stage | Script | Input | Checks |
|-------|--------|-------|--------|
| OCR | `evals/run_ocr_eval.py` | PDF path | Required phrases in OCR text |
| Extract | `evals/run_extract_eval.py` | Golden OCR text | Structured field checks |
| Proposal | `evals/run_proposal_eval.py` | Golden extract JSON | Non-empty `ReviewPackage` |

Cases: `evals/court/cases.yaml` — `case_1`, `case_2`, `doc_viewer` (PDFs in `fixtures/court/`).

Bootstrap court goldens:

```bash
python evals/bootstrap_goldens.py
```

Writes:

- `evals/court/ocr/goldens/*.ocr.txt`
- `evals/court/extract/goldens/*.json`
- `evals/court/cases.yaml`

## Classification (`evals/classification/`)

| Stage | Script | Input | Checks |
|-------|--------|-------|--------|
| Classification | `evals/run_classification_eval.py` | Golden OCR text | Account type + evidence phrases |

Cases: `evals/classification/cases.yaml` (21 consumer PDF fixtures).

Bootstrap classification goldens:

```bash
python evals/bootstrap_classification_goldens.py
python evals/bootstrap_classification_goldens.py --ocr --skip-classify   # live olmocr2 (slow)
```

## Portfolio (`evals/portfolio/`)

| Stage | Script | Input | Checks |
|-------|--------|-------|--------|
| Portfolio | `evals/run_portfolio_eval.py` | `sample.dat` + docs + synthetic codes | Source path + archetype |

Cases: `evals/portfolio/cases.yaml` (12 accounts — 4 unique client-code, 8 LLM).

```bash
python evals/run_portfolio_eval.py --unique-only   # offline client-code path
python evals/run_portfolio_eval.py                 # full suite (needs Ollama for LLM cases)
python evals/run_portfolio_eval.py --case SL-24001 --case AL-88021
```

`--unique-only` asserts `source=client_code` without Ollama. Full runs also exercise ambiguous/missing LLM cases (needs Ollama + docs under `fixtures/portfolio/`).

## Run evals

```bash
python evals/run_ocr_eval.py
python evals/run_extract_eval.py
python evals/run_proposal_eval.py
python evals/run_classification_eval.py
python evals/run_portfolio_eval.py
```

Extract and classification evals use golden OCR text (fast, isolates the LLM). OCR evals re-run olmocr2 against PDFs (slow). Portfolio evals mix client-code short-circuits with live LLM for ambiguous/missing.

```bash
python evals/run_ocr_eval.py              # live olmocr2 (default)
python evals/run_ocr_eval.py --use-cache  # sidecar cache only (fast smoke test)
```

Requires Ollama with models from `.env`.

## Regression snapshots (default: on)

Each eval run writes artifacts under `evals/runs/{suite}/{timestamp}/`:

| Suite | Files per case |
|-------|----------------|
| `ocr` | `ocr.txt`, `meta.json` |
| `extract` | `extraction.json`, `meta.json` |
| `proposal` | `review_package.json`, `meta.json` |
| `classification` | `classification.json`, `meta.json` |
| `portfolio` | `account.json`, `meta.json` (+ `_batch/summary.json` with usage totals) |

Portfolio and classification snapshots include timing/token metrics:

- per-case `meta.json`: `task_duration_s`, `llm_usage`, `ocr_usage` (portfolio), `models`
- portfolio `_batch/summary.json`: `batch_duration_s`, `usage_totals`, `models`

Each run also writes `manifest.json` (pass/fail, git sha, file list). The latest run path is recorded in `evals/runs/{suite}/latest.txt`.

```bash
python evals/run_extract_eval.py              # snapshots on by default
python evals/run_extract_eval.py --no-snapshot
python evals/run_proposal_eval.py --snapshot-label before-prompt-change

# Compare two runs (dir path or suite name for latest)
python evals/compare_snapshots.py extract/20260101T120000Z extract/latest
python evals/compare_snapshots.py evals/runs/extract/RUN_A evals/runs/extract/RUN_B
```

Snapshots do **not** fail the eval — they are for human diff and regression review alongside the existing checklist assertions.
