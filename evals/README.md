# Court document eval sets

Three fixture PDFs, three eval stages:

| Stage | Script | Input | Checks |
|-------|--------|-------|--------|
| OCR | `evals/run_ocr_eval.py` | PDF path | Required phrases in OCR text |
| Extract | `evals/run_extract_eval.py` | Golden OCR text | Structured field checks |
| Classification | `evals/run_classification_eval.py` | Golden OCR text fixtures | Account type + evidence phrases |

## Cases

- `case_1` — `fixtures/case 1.pdf`
- `case_2` — `fixtures/case 2.pdf`
- `doc_viewer` — `fixtures/DocViewer.pdf`

Classification cases are defined in `evals/classification/cases.yaml` (21 consumer PDF fixtures).

Bootstrap classification goldens:

```bash
python evals/bootstrap_classification_goldens.py
python evals/bootstrap_classification_goldens.py --ocr   # live olmocr2 (slow)
```

## Bootstrap goldens (first time or after OCR model change)

```bash
python evals/bootstrap_goldens.py
```

This writes:

- `evals/ocr/goldens/*.ocr.txt` — OCR reference text
- `evals/extract/goldens/*.json` — reference extractions
- `evals/cases.yaml` — required phrases and extract checks per case

Review and edit `cases.yaml` after bootstrapping — especially `required_phrases` and `extract_checks`.

## Run evals

```bash
python evals/run_ocr_eval.py
python evals/run_extract_eval.py
python evals/run_classification_eval.py
```

Extract and classification evals use golden OCR text (fast, isolates the LLM). OCR evals re-run olmocr2 against PDFs (slow).

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
