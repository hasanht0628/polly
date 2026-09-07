# Pollack

Local document pipeline for law-firm workflows. You give it a file; it returns structured JSON a person can review.

| Job | Input | Output |
|-----|-------|--------|
| Court calendar | Court PDF or `.eml` | `ReviewPackage` — calendar events + flagged items |
| Account classification | Consumer PDF | One of seven account archetypes |
| Portfolio classification | Fixed-width `.dat` + optional PDF folders | One result per account |
| Redaction | PDF(s) or a folder | `*.redacted.pdf` + a JSON manifest |

**All documentation is in one place:** [docs/guide.md](docs/guide.md)

That guide is written for Windows (PowerShell), explains every workflow in plain language, and shows input/output diagrams plus sample JSON.

## Prerequisites (Windows)

- **Python 3.12+**
- **[Ollama](https://ollama.com/)** running locally:

  ```powershell
  irm https://ollama.com/install.ps1 | iex
  ollama pull qwen2.5:7b
  ollama pull richardyoung/olmocr2:7b-q8
  ```

- Settings from [`.env.example`](.env.example): `qwen2.5:7b` for extraction/classification, `richardyoung/olmocr2:7b-q8` for page OCR

## Quick start (PowerShell)

From the project root, with a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env

python scripts\check_ollama.py
python scripts\extract_court_doc.py "fixtures\court\case 1.pdf" --pretty
python scripts\run_court_workflow.py --pdf "fixtures\court\case 1.pdf" --pretty
```

The first OCR run on a PDF is slow (olmocr2, one page at a time). Results are cached as `{same-name}.ocr.txt` next to the PDF.

If `Activate.ps1` is blocked, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Project layout

| Directory | Purpose |
|-----------|---------|
| [`court/`](court/) | Court extraction, normalization, schemas |
| [`workflows/`](workflows/) | Court calendar, account classification, portfolio, redaction, email intake |
| [`documents/`](documents/) | Shared OCR, ingest, PDF download, extract profiles |
| [`redaction/`](redaction/) | Detect / locate / apply PII redactions |
| [`agents/`](agents/) | LLM config, supervisor, audit log |
| [`knowledge/`](knowledge/) | Client manuals and officer-code tables |
| [`classification/`](classification/) | Account-type schemas and baseline taxonomy |
| [`portfolio/`](portfolio/) | `.dat` parsing, PDF location, ambiguous-case agent |
| [`evals/`](evals/) | Eval harness, goldens, snapshots |
| [`scripts/`](scripts/) | CLI entry points |
| [`tests/`](tests/) | Pytest suite (mostly offline) |
| [`fixtures/`](fixtures/) | Sample PDFs and test data (local; mostly gitignored) |
| [`docs/guide.md`](docs/guide.md) | Complete guide |

## Common commands

```powershell
pytest tests\ -q

python evals\run_proposal_eval.py
python evals\run_extract_eval.py
python evals\run_ocr_eval.py --use-cache
python evals\bootstrap_goldens.py
python evals\compare_snapshots.py proposal\latest proposal\before-change
```
