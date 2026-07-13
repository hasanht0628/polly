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
python scripts/extract_court_doc.py "fixtures/court/case 1.pdf" --pretty
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
python scripts/run_court_workflow.py --pdf "fixtures/court/case 1.pdf" --pretty
python scripts/run_court_workflow.py --pdf "fixtures/court/case 1.pdf" --output review.json
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
python scripts/propose_calendar.py "fixtures/court/case 1.pdf" \
  --from-golden evals/court/extract/goldens/case_1.json --pretty
```

---

### `scripts/run_account_classification.py`

Consumer PDF → account classification workflow with audit logging.

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

### `scripts/run_portfolio_classification.py`

Batch classify accounts from a portfolio `.dat` file. Unique officer-code mappings short-circuit; ambiguous/missing cases use a tool-using PDF agent when `--docs-root` is provided.

```
python scripts/run_portfolio_classification.py --dat DAT [--docs-root DOCS]
                                              [--codes CODES] [--client-id ID]
                                              [--no-cache] [--pretty]
```

| Argument / flag | Description |
|-----------------|-------------|
| `--dat` | Portfolio `.dat` path |
| `--docs-root` | Root with `PLMTDOCS_*/<account_id>/` PDF folders; `PLMTDOCS_YYMMDD.zip` archives are auto-extracted on run |
| `--codes` | YAML officer→product→archetype table (default `knowledge/client_codes/default.yaml`) |
| `--client-id` | Client id for LLM taxonomy context |
| `--no-cache` | Ignore OCR sidecars |
| `--pretty` | Pretty-print JSON |

**Output:** `PortfolioClassificationBatch` JSON.

**Example:**

```bash
python scripts/run_portfolio_classification.py \
  --dat fixtures/portfolio/sample.dat \
  --docs-root fixtures/portfolio \
  --codes knowledge/client_codes/synthetic_test.yaml \
  --pretty
```

For the synthetic portfolio fixtures, pass `--codes knowledge/client_codes/synthetic_test.yaml` so officer codes resolve against the TEST mapping table: four unique codes (`TSTSL1`, `TSTPL1`, `TSTRI1`, `TSTAL1`) short-circuit; ambiguous `TSTAMB` and missing `TSTMSS` fall through to the PDF/LLM agent when `--docs-root` is set. Omit `--codes` (or point at `default.yaml`) for real client manuals.

Eval harness (source + archetype checks per account):

```bash
python evals/run_portfolio_eval.py
```

---

### `scripts/inspect_dat.py`

Dump record-type counts, officer-code lengths, and sample parsed cases from a `.dat` file (for locking fixed-width offsets).

```
python scripts/inspect_dat.py DAT [--limit N] [--json]
```

---

### `scripts/find_account_pdfs.py`

Locate account folders/PDFs for a `.dat` case id under a docs root. Extracts any `PLMTDOCS_YYMMDD.zip` archives under the root before lookup.

```
python scripts/find_account_pdfs.py DOCS_ROOT CASE_ID [--pretty]
```

---

### `scripts/debug_classify.py`

Isolated single-call test of the archetype classifier (offline, local Ollama). The fast way to debug *accuracy* without the full agentic loop: feeds one document's text straight to `classify_document_text` and prints the result + token usage.

```
python scripts/debug_classify.py (--ocr OCR | --pdf PDF) [--client-id ID]
                                 [--candidates LIST] [--officer-code CODE]
                                 [--plaintiff P] [--notes N] [--no-cache]
```

| Argument / flag | Description |
|-----------------|-------------|
| `--ocr` | Path to a `.ocr.txt` / plain-text document (mutually exclusive with `--pdf`) |
| `--pdf` | Path to a PDF (OCR'd, honoring the `.ocr.txt` cache) |
| `--client-id` | Client id for taxonomy context (default `portfolio`) |
| `--candidates` | Comma-separated `archetype_candidates` to bias the classifier, e.g. `auto_deficiency,fintech` |
| `--officer-code` / `--plaintiff` / `--notes` | Optional case context added to the prompt |
| `--no-cache` | Force live OCR for `--pdf` |

**Example:**

```bash
python -u scripts/debug_classify.py \
  --ocr data/docs_root/ACME/ACME_statement.ocr.txt \
  --candidates auto_deficiency,fintech
```

---

### `scripts/debug_ambiguous_agent.py`

Instrumented single-case run of the ambiguous portfolio agent (offline, local Ollama). Shows step by step whether the model calls tools, what each tool returned, where time is spent, and the final classification. Use it to debug the agentic PDF path on real portfolio data.

```
python scripts/debug_ambiguous_agent.py [--case-id ID] [--dat DAT] [--docs DOCS]
                                        [--codes CODES] [--case-map MAP]
                                        [--client-id ID] [--no-cache] [--clip N]
```

| Argument / flag | Description |
|-----------------|-------------|
| `--case-id` | 9-char case id from the `.dat` file (default `000880021`) |
| `--dat` | Portfolio `.dat` path (default synthetic fixture) |
| `--docs` | Docs root with account folders (default `fixtures/portfolio`) |
| `--codes` | Officer-code YAML (default `knowledge/client_codes/synthetic_test.yaml`) |
| `--case-map` | Optional `case_id` → account-folder alias map |
| `--no-cache` | Force live OCR (ignore `.ocr.txt` sidecars) |
| `--clip` | Max chars printed per tool result (default 300) |

**Example (real data):**

```bash
python -u scripts/debug_ambiguous_agent.py \
  --dat data/portfolio.dat --docs data/docs_root \
  --codes knowledge/client_codes/default.yaml --case-id 000123456
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

Requires Ollama with `OLLAMA_MODEL`. Uses `evals/court/ocr/goldens/*.ocr.txt` as input.

---

### `evals/run_proposal_eval.py`

Run proposal eval on extract goldens (offline — no LLM).

```
python evals/run_proposal_eval.py [-h] [--snapshot | --no-snapshot]
                                  [--snapshot-label SNAPSHOT_LABEL]
```

Maps `evals/court/extract/goldens/*.json` → `ReviewPackage` and checks output is non-empty.

---

### `evals/run_portfolio_eval.py`

Run portfolio classification evals on `fixtures/portfolio/sample.dat` with synthetic TEST codes.

```
python evals/run_portfolio_eval.py [-h] [--case SLUG] [--unique-only] [--no-cache]
                                   [--snapshot | --no-snapshot]
                                   [--snapshot-label SNAPSHOT_LABEL]
```

| Flag | Description |
|------|-------------|
| `--case SLUG` | Run only these account slugs (repeatable), e.g. `SL-24001` |
| `--unique-only` | Only unique client-code cases (offline, no Ollama) |
| `--no-cache` | Ignore OCR sidecars for LLM-path PDF reads |
| `--snapshot` / `--no-snapshot` | Write regression snapshots (default: on) |

Checks per account: `expected_source` (`client_code` / `llm`) and `expected_archetype`. Unique cases need no Ollama; ambiguous/missing cases need Ollama + docs under `fixtures/portfolio/`.

Snapshots record timing/token metrics for local vs OpenAI comparison:

- per-case `meta.json`: `task_duration_s`, `llm_usage`, `ocr_usage`, `total_usage`, `models`
- `_batch/summary.json`: `batch_duration_s`, `usage_totals`, `models`

The runner also prints a usage table (duration + LLM/OCR tokens) after the path summary.

**Example:**

```bash
python evals/run_portfolio_eval.py --unique-only
python evals/run_portfolio_eval.py
python evals/run_portfolio_eval.py --case SL-24001 --case AL-88021
```

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

package = await run_court_workflow(pdf_path=Path("fixtures/court/case 1.pdf"))
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
    Path("fixtures/court/case 1.pdf"),
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
