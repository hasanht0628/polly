# Sample court PDFs for extraction testing

Add redacted sample PDFs here. Do not commit unredacted PII.

## Suggested names

- `scheduling_order_01.pdf`
- `trial_notice_virtual.pdf`
- `docket_sounding_notice.pdf`

## Run extract

From the project root:

```bash
python scripts/extract_court_doc.py "fixtures/case 1.pdf" --pretty
```

OCR output is cached as `fixtures/case 1.ocr.txt` after the first run. Use `--refresh-ocr` to re-run olmocr2.

Requires Ollama running with models from `.env`:

- `OLLAMA_MODEL_OCR` (olmocr2) — reads every page
- `OLLAMA_MODEL` (qwen2.5) — structured extraction
