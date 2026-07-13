# Pollack

Court-document pipeline for law-firm workflows: PDF → OCR → structured extraction → scheduling output (`ReviewPackage` JSON). Also includes consumer account classification (seven firm archetypes) and a portfolio `.dat` workflow that resolves officer codes then falls back to PDF/LLM when mappings are ambiguous.

## Prerequisites

- **Python 3.12+**
- **[Ollama](https://ollama.com/)** running locally. On Windows (PowerShell):

  ```powershell
  irm https://ollama.com/install.ps1 | iex
  ```
- Two models (see [`.env.example`](.env.example)):
  - `qwen2.5:7b` — structured extraction and classification
  - `richardyoung/olmocr2:7b-q8` — page OCR

## Quick start

```bash
# Clone or unzip the project, then from the project root:
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env
ollama pull qwen2.5:7b
ollama pull richardyoung/olmocr2:7b-q8

python scripts/check_ollama.py
python scripts/extract_court_doc.py "fixtures/court/case 1.pdf" --pretty
python scripts/run_court_workflow.py --pdf "fixtures/court/case 1.pdf" --pretty
```

The first OCR run on a PDF is slow (olmocr2 per page). Results are cached as `fixtures/court/case 1.ocr.txt` next to the PDF.

## Project layout

| Directory | Purpose |
|-----------|---------|
| [`court/`](court/) | Court extraction, normalization, schemas |
| [`workflows/`](workflows/) | Court calendar pipeline, account classification, email intake |
| [`documents/`](documents/) | Shared OCR, ingest, PDF download, extract profile registry |
| [`agents/`](agents/) | LLM config, extract helpers, supervisor, audit log, tool registry |
| [`knowledge/`](knowledge/) | Client manual storage and retrieval |
| [`classification/`](classification/) | Product classification schemas |
| [`evals/`](evals/) | Eval harness, goldens, regression snapshots |
| [`scripts/`](scripts/) | CLI entry points |
| [`tests/`](tests/) | Pytest suite (mostly offline) |
| [`fixtures/`](fixtures/) | Sample PDFs and test data |

## Documentation

| Doc | Contents |
|-----|----------|
| [Architecture](docs/architecture.md) | Layers, data flow, schemas, runtime paths |
| [Development guide](docs/development.md) | Setup, testing, evals, debugging |
| [CLI reference](docs/cli-reference.md) | All scripts and flags |
| [Evals](evals/README.md) | OCR / extract / proposal eval stages, snapshots |
| [Fixtures](fixtures/README.md) | Sample PDF usage |

## Common commands

```bash
# Offline tests (no Ollama)
pytest tests/ -q

# Evals
python evals/run_proposal_eval.py              # offline mapper check
python evals/run_extract_eval.py               # live LLM on golden OCR
python evals/run_ocr_eval.py --use-cache       # fast OCR smoke test

# Bootstrap eval goldens (first time or after model change)
python evals/bootstrap_goldens.py

# Compare regression snapshots
python evals/compare_snapshots.py proposal/latest proposal/before-change
```
