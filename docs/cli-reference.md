# CLI reference

All command-line entry points and programmatic APIs.

Run from the **project root** with the virtualenv activated.

## Scripts

### `scripts/extract_court_doc.py`

Extract structured case data from a court PDF (OCR + LLM).

```
python scripts/extract_court_doc.py [-h] [--pretty] [--refresh-ocr] pdf
```

| Argument / flag | Description |
|-----------------|-------------|
| `pdf` | Path to court PDF |
| `--pretty` | Pretty-print JSON |
| `--refresh-ocr` | Re-run olmocr2 even if `.ocr.txt` cache exists |

**Output:** `CaseExtraction` JSON to stdout.

**Example:**

```bash
python scripts/extract_court_doc.py "fixtures/case 1.pdf" --pretty
```

---

### `scripts/run_court_workflow.py`

Full court pipeline → `ReviewPackage` JSON.

```
python scripts/run_court_workflow.py [-h] (--pdf PDF | --email EMAIL)
                                     [--pretty] [--output OUTPUT] [--refresh-ocr]
```

| Argument / flag | Description |
|-----------------|-------------|
| `--pdf PDF` | Path to court PDF |
| `--email EMAIL` | Path to `.eml` intake file |
| `--pretty` | Pretty-print JSON |
| `--output OUTPUT` | Write JSON to file instead of stdout |
| `--refresh-ocr` | Re-run OCR (ignore sidecar cache) |

**Output:** `ReviewPackage` JSON.

**Examples:**

```bash
python scripts/run_court_workflow.py --pdf "fixtures/case 1.pdf" --pretty
python scripts/run_court_workflow.py --pdf "fixtures/case 1.pdf" --output review.json
python scripts/run_court_workflow.py --email intake.eml --pretty
```

---

### `scripts/propose_calendar.py`

Map extraction to schedulable calendar output (extract + map, or golden-only).

```
python scripts/propose_calendar.py [-h] [--pretty] [--from-golden FROM_GOLDEN]
                                   [--refresh-ocr] pdf
```

| Argument / flag | Description |
|-----------------|-------------|
| `pdf` | Court PDF path |
| `--pretty` | Pretty-print JSON |
| `--from-golden FROM_GOLDEN` | Use extract golden JSON instead of live extract |
| `--refresh-ocr` | Re-run OCR |

**Example (offline):**

```bash
python scripts/propose_calendar.py "fixtures/case 1.pdf" \
  --from-golden evals/extract/goldens/case_1.json --pretty
```

---

### `scripts/classify_document.py`

Classify a consumer document (wraps the account classification workflow).

```
python scripts/classify_document.py [-h] [--pretty] [--refresh-ocr] [--consumer-id CONSUMER_ID] client_id pdf
```

| Argument / flag | Description |
|-----------------|-------------|
| `client_id` | Client whose manual/taxonomy to use |
| `pdf` | Consumer document PDF |
| `--consumer-id` | Optional consumer identifier |
| `--pretty` | Pretty-print JSON |
| `--refresh-ocr` | Re-run OCR |

**Output:** `AccountClassificationPackage` JSON. Works with or without an ingested manual (baseline taxonomy is always applied).

**Example:**

```bash
python scripts/classify_document.py acme fixtures/classification/consumer/credit_card_statement.pdf --pretty
```

---

### `scripts/run_account_classification.py`

Full consumer PDF → account classification workflow with audit logging.

```
python scripts/run_account_classification.py [-h] [--pretty] [--refresh-ocr] [--consumer-id CONSUMER_ID] [--output OUTPUT] client_id pdf
```

| Argument / flag | Description |
|-----------------|-------------|
| `client_id` | Client whose manual/taxonomy to use |
| `pdf` | Consumer document PDF |
| `--consumer-id` | Optional consumer identifier |
| `--output` | Write JSON to file |
| `--pretty` | Pretty-print JSON |
| `--refresh-ocr` | Re-run OCR |

**Example:**

```bash
python scripts/run_account_classification.py acme fixtures/classification/consumer/mortgage_statement.pdf --consumer-id C-12345 --pretty
```

---

### `scripts/ingest_client_manual.py`

Ingest a client manual PDF → taxonomy + chunk index.

```
python scripts/ingest_client_manual.py [-h] [--pretty] [--refresh-ocr] client_id pdf
```

| Argument / flag | Description |
|-----------------|-------------|
| `client_id` | Client identifier (used as storage key) |
| `pdf` | Client manual PDF |
| `--pretty` | Pretty-print JSON |
| `--refresh-ocr` | Re-run OCR |

**Output:** `ClientTaxonomy` JSON. Persists to `knowledge/client_manuals/{client_id}/`.

**Example:**

```bash
python scripts/ingest_client_manual.py acme path/to/manual.pdf --pretty
```

---

### `scripts/check_ollama.py`

Smoke test Ollama connectivity and the configured extract model.

```bash
python scripts/check_ollama.py
```

Prints installed models and runs a one-message chat test. Exits non-zero if `OLLAMA_MODEL` is not installed.

---

## Eval runners

See also [`evals/README.md`](../evals/README.md).

### `evals/run_ocr_eval.py`

Run OCR evals against fixture PDFs.

```
python evals/run_ocr_eval.py [-h] [--use-cache] [--case SLUG]
                             [--snapshot | --no-snapshot]
                             [--snapshot-label SNAPSHOT_LABEL]
```

| Flag | Description |
|------|-------------|
| `--use-cache` | Use sidecar `.ocr.txt` next to PDFs (fast, skips live olmocr2) |
| `--case SLUG` | Run only specific case(s); repeatable |
| `--snapshot` / `--no-snapshot` | Write regression snapshots (default: on) |
| `--snapshot-label LABEL` | Named run folder instead of UTC timestamp |

**Example:**

```bash
python evals/run_ocr_eval.py --use-cache
python evals/run_ocr_eval.py --case case_1
```

---

### `evals/run_extract_eval.py`

Run extract evals on golden OCR text (isolates LLM quality from OCR).

```
python evals/run_extract_eval.py [-h] [--snapshot | --no-snapshot]
                                 [--snapshot-label SNAPSHOT_LABEL]
```

Requires Ollama with `OLLAMA_MODEL`. Uses `evals/ocr/goldens/*.ocr.txt` as input.

---

### `evals/run_proposal_eval.py`

Run proposal eval on extract goldens (offline — no LLM).

```
python evals/run_proposal_eval.py [-h] [--snapshot | --no-snapshot]
                                  [--snapshot-label SNAPSHOT_LABEL]
```

Maps `evals/extract/goldens/*.json` → `ReviewPackage` and checks output is non-empty.

---

### `evals/bootstrap_goldens.py`

Regenerate OCR goldens, extract goldens, and `cases.yaml`.

```
python evals/bootstrap_goldens.py [-h] [--extract-only]
```

| Flag | Description |
|------|-------------|
| `--extract-only` | Skip OCR; use existing OCR goldens, re-run extract + cases.yaml |

**Example:**

```bash
python evals/bootstrap_goldens.py
python evals/bootstrap_goldens.py --extract-only
```

---

### `evals/compare_snapshots.py`

Compare two regression snapshot runs.

```
python evals/compare_snapshots.py [-h] baseline current
```

| Argument | Description |
|----------|-------------|
| `baseline` | Run directory, or suite name (uses `latest.txt`) |
| `current` | Run directory, or suite name |

**Examples:**

```bash
python evals/compare_snapshots.py proposal/latest proposal/before-change
python evals/compare_snapshots.py extract/20260101T120000Z extract/latest
python evals/compare_snapshots.py evals/runs/extract/RUN_A evals/runs/extract/RUN_B
```

---

## Programmatic APIs

### Court workflow

```python
from pathlib import Path
from agents.supervisor import run_court_workflow, format_scheduling_output

package = await run_court_workflow(pdf_path=Path("fixtures/case 1.pdf"))
text = format_scheduling_output(package, pretty=True)
```

Also accepts `email_path` for `.eml` intake. Set `use_cache=False` to force fresh OCR.

Lower-level entry points in [`workflows/court_calendar/run.py`](../workflows/court_calendar/run.py):
- `run_court_workflow_from_pdf(pdf_path, use_cache=True)`
- `run_court_workflow_from_email(email_path, use_cache=True)`

### Extract profiles

```python
from pathlib import Path
from documents.profiles.registry import extract_document, list_profiles

print(list_profiles())  # court_calendar, client_manual_taxonomy, product_classification

result = await extract_document(
    Path("fixtures/case 1.pdf"),
    profile="court_calendar",
    use_cache=True,
)
```

Pass `context={...}` for profiles that need extra input (e.g. `product_classification` expects taxonomy and manual passages).

### Mapper only (no LLM)

```python
from court.schemas import CaseExtraction
from workflows.court_calendar.map_extraction import map_extraction_to_review_package

extraction = CaseExtraction.model_validate_json(path.read_text())
package = map_extraction_to_review_package(extraction, pdf_path=path)
```
