# Development guide

Day-to-day setup, testing, eval workflow, and debugging for Pollack contributors.

## Environment setup

### 1. Python virtualenv

```bash
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .\.venv\Scripts\Activate.ps1     # Windows PowerShell
pip install -r requirements.txt
```

Requires **Python 3.12+**. Dependencies are listed in [`requirements.txt`](../requirements.txt) — no `pyproject.toml`.

### 2. Ollama and models

Install [Ollama](https://ollama.com/) and ensure it is running, then pull models:

```bash
ollama pull qwen2.5:7b
ollama pull richardyoung/olmocr2:7b-q8
```

### 3. Environment variables

Copy the template and adjust if needed:

```bash
cp .env.example .env
```

| Variable | Purpose | Default |
|----------|---------|---------|
| `OLLAMA_BASE_URL` | Ollama OpenAI-compatible API | `http://localhost:11434/v1` |
| `OLLAMA_MODEL` | Structured extraction (qwen) | `qwen2.5:7b` |
| `OLLAMA_MODEL_OCR` | Page OCR (olmocr2) | `richardyoung/olmocr2:7b-q8` |
| `USE_OPENAI` | Temporary switch: all agents use OpenAI | `false` |
| `OPENAI_API_KEY` | Required when `USE_OPENAI=true` | — |
| `OPENAI_MODEL` | OpenAI extract / classify model | `gpt-4o-mini` |
| `OPENAI_MODEL_OCR` | OpenAI vision OCR model | `gpt-4o-mini` |

Loaded via `python-dotenv` in scripts, evals, and [`agents/config.py`](../agents/config.py).

To speed up local testing, set `USE_OPENAI=true` in `.env`. Flip it back to `false` to return to Ollama.

### 4. Smoke test

```bash
python scripts/check_ollama.py
```

Should list installed models and print `Smoke test: ok`.

## Running without LLM

Most unit tests and the proposal eval do not call Ollama:

```bash
pytest tests/ -q
python evals/run_proposal_eval.py
```

Offline tests cover normalization, workflow mapping, email parsing, eval case loading, snapshot writer, platform registry, and classification fixtures.

**Note:** `test_ocr_goldens_exist_and_contain_phrases` requires bootstrap goldens to exist under `evals/court/ocr/goldens/`. On a fresh machine, run bootstrap first (see below).

## Running with LLM

### Extract one PDF

```bash
python scripts/extract_court_doc.py "fixtures/court/case 1.pdf" --pretty
```

First run OCRs every page (~minutes). Subsequent runs use `fixtures/court/case 1.ocr.txt` unless you pass `--refresh-ocr`.

### Full workflow

```bash
python scripts/run_court_workflow.py --pdf "fixtures/court/case 1.pdf" --pretty
python scripts/run_court_workflow.py --pdf "fixtures/court/case 1.pdf" --output review.json
```

### Email intake

```bash
python scripts/run_court_workflow.py --email path/to/intake.eml --pretty
```

## Eval workflow

Full details in [`evals/README.md`](../evals/README.md). Summary:

| Stage | Script | Needs Ollama? | Input |
|-------|--------|---------------|-------|
| Proposal | `evals/run_proposal_eval.py` | No | Golden extract JSON |
| Extract | `evals/run_extract_eval.py` | Yes (qwen) | Golden OCR text |
| OCR | `evals/run_ocr_eval.py` | Yes (olmocr2) | Live PDF |

### Checklist vs golden equality

Evals use **checklist assertions**, not strict JSON equality against goldens. This is intentional — LLM output varies run-to-run. Goldens are reference/bootstrap material; evaluators check things like case number presence, minimum event count, required OCR phrases.

### Bootstrap goldens

First-time setup or after an OCR/extract model change:

```bash
python evals/bootstrap_goldens.py
```

Writes:
- `evals/court/ocr/goldens/*.ocr.txt`
- `evals/court/extract/goldens/*.json`
- `evals/court/cases.yaml` (derived phrases and extract checks)

Review `evals/court/cases.yaml` after bootstrapping — especially `required_phrases` and `extract_checks`.

Use `--extract-only` to skip OCR and regenerate extract goldens from existing OCR goldens.

### Regression snapshots

Each eval run saves artifacts under `evals/runs/{suite}/{timestamp}/` by default. Snapshots do **not** fail the eval — they are for human diff review.

```bash
python evals/run_extract_eval.py --snapshot-label before-prompt-change
python evals/compare_snapshots.py extract/before-prompt-change extract/latest
```

Disable with `--no-snapshot`.

## Adding a new eval case

1. Add a redacted PDF to [`fixtures/`](../fixtures/)
2. Register it in [`evals/court/cases.py`](../evals/court/cases.py) or run bootstrap (which updates `cases.yaml`)
3. Run `python evals/bootstrap_goldens.py`
4. Review and edit `evals/court/cases.yaml` if derived checks need tuning
5. Run all three eval stages

See [`fixtures/README.md`](../fixtures/README.md) for naming conventions.

## Debugging tips

### Ollama stuck on "Stopping…"

Restart Ollama (`ollama serve` or restart from the system tray). Common when olmocr2 hangs mid-OCR.

### Wrong scheduling output

1. Open `ReviewPackage.flagged_items` — each item has a `reason` explaining why it was not auto-scheduled
2. Trace `source_quote` on events/deadlines back to OCR text in `{pdf}.ocr.txt`
3. Compare extract output: `python scripts/extract_court_doc.py "fixtures/court/case 1.pdf" --pretty`

### Mapper decisions

Read [`workflows/court_calendar/map_extraction.py`](../workflows/court_calendar/map_extraction.py). Events need both `date` and `time` to become `SchedulableEvent`. Relative deadlines always go to `flagged_items`.

### Regression comparison

```bash
python evals/compare_snapshots.py proposal/baseline proposal/current
```

Supports suite names (resolves via `evals/runs/{suite}/latest.txt`) or full directory paths.

### Re-run OCR from scratch

```bash
python scripts/extract_court_doc.py "fixtures/court/case 1.pdf" --refresh-ocr --pretty
```

Deletes reliance on sidecar cache for that run (overwrites `.ocr.txt`).

## Cold machine setup

When moving the project to a new machine without Mac caches:

**Include:** source code, fixture PDFs, `requirements.txt`, `.env.example`, `evals/court/cases.yaml`

**Exclude:** `.venv/`, `fixtures/**/*.ocr.txt`, `evals/court/ocr/goldens/*`, `evals/court/extract/goldens/*`, `evals/runs/*`

On the new machine:

1. Install Python 3.12+ and Ollama; pull both models
2. `python -m venv .venv` → activate → `pip install -r requirements.txt`
3. Copy `.env.example` → `.env`
4. `python evals/bootstrap_goldens.py` (live OCR + extract — expect ~40+ min on CPU)
5. `pytest tests/ -q` → run evals

## Test layout

| File | Coverage |
|------|----------|
| [`tests/test_normalize.py`](../tests/test_normalize.py) | Extraction normalization |
| [`tests/test_workflows.py`](../tests/test_workflows.py) | Mapper, email parser |
| [`tests/test_eval_offline.py`](../tests/test_eval_offline.py) | Eval cases, goldens, phrase matcher |
| [`tests/test_eval_snapshots.py`](../tests/test_eval_snapshots.py) | Snapshot writer and compare |
| [`tests/test_platform.py`](../tests/test_platform.py) | Profile registry, audit log, manual store |
| [`tests/test_classification_offline.py`](../tests/test_classification_offline.py) | Classification fixtures |

Run from project root: `pytest tests/ -q`
