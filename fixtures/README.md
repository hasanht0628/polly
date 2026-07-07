# Sample fixtures for extraction and classification testing

**Git policy:** Everything under `fixtures/` is gitignored except this README and `.gitkeep` markers. Copy sample PDFs and synthetic fixtures here locally; do not commit unredacted PII.

## Court PDFs

Add redacted sample court PDFs at the repo root of this folder, e.g.:

- `case 1.pdf`
- `scheduling_order_01.pdf`

```bash
python scripts/extract_court_doc.py "fixtures/case 1.pdf" --pretty
```

OCR sidecars (`*.ocr.txt`) are created beside the PDF on first run.

## Consumer classification PDFs

Real consumer document test set:

```
fixtures/classification/consumer/pdfs/
```

Currently holds `sample_001.pdf` … `sample_021.pdf` (local only).

Run classification:

```bash
python scripts/run_account_classification.py acme "fixtures/classification/consumer/pdfs/sample_001.pdf" --pretty
```

## Synthetic classification fixtures

Offline tests and evals also use plain-text statement fixtures:

```
fixtures/classification/consumer/*.txt
fixtures/classification/consumer/*_classification.json
fixtures/classification/manuals/
```

Register labeled cases in `evals/classification/cases.yaml`.

## Prerequisites

Requires Ollama with models from `.env`:

- `OLLAMA_MODEL_OCR` (olmocr2) — reads every page
- `OLLAMA_MODEL` (qwen2.5) — structured extraction / classification
