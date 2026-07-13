# Sample fixtures for extraction and classification testing



**Git policy:** Everything under `fixtures/` is gitignored except this README and `.gitkeep` markers. Copy sample PDFs and synthetic fixtures here locally; do not commit unredacted PII.



## Court PDFs



Redacted sample court PDFs:



```

fixtures/court/

```



Currently holds `case 1.pdf`, `case 2.pdf`, and `DocViewer.pdf` (local only).



```bash

python scripts/extract_court_doc.py "fixtures/court/case 1.pdf" --pretty

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



## Portfolio `.dat` + docs (local)

Synthetic layout for the portfolio classification workflow (gitignored locally):

```
fixtures/portfolio/sample.dat
fixtures/portfolio/case_id_map.yaml
fixtures/portfolio/<date>/PLMTDOCS_<date>.zip
fixtures/portfolio/<date>/PLMTDOCS_<date>/<account_id>/*.pdf
```

`sample.dat` is a fixed-width synthetic file (12 cases: student / personal / retail / auto) with record types `01`/`02`/`09`. Manifest account ids such as `SL-24001` do not fit the 9-char case_id field; `case_id_map.yaml` maps each padded numeric `case_id` to account id, type, consumer, plaintiff, officer code, and `resolve_path` (`unique` / `ambiguous` / `missing`). PDF folders use the manifest `account_id`; the locator resolves them via that map.

Officer codes are **TEST-only** from `knowledge/client_codes/synthetic_test.yaml`:

| Path | Officer codes | Cases |
|------|---------------|-------|
| **unique** (client-code short-circuit, no LLM) | `TSTSL1`, `TSTPL1`, `TSTRI1`, `TSTAL1` | 4 accounts (one per archetype) |
| **ambiguous** (LLM when `--docs-root` set) | `TSTAMB` | SL-24002, CL-55014, RI-73011, AL-88021, SL-24003 |
| **missing** (LLM when `--docs-root` set) | `TSTMSS` (not in YAML) | PL-55015, RI-73012, AL-88023 |

PLMTDOCS archives are zip files named `PLMTDOCS_<date>.zip` where `<date>` is a six-digit stamp (`YYMMDD`, e.g. `PLMTDOCS_250708.zip`). On workflow or CLI run, each zip is auto-extracted to a sibling folder (`PLMTDOCS_<date>/`) before PDF lookup.

Exercise both paths (unique short-circuit + LLM fallback for ambiguous/missing):

```bash
python scripts/inspect_dat.py fixtures/portfolio/sample.dat
python scripts/find_account_pdfs.py fixtures/portfolio 000240001 --pretty
python scripts/run_portfolio_classification.py \
  --dat fixtures/portfolio/sample.dat \
  --docs-root fixtures/portfolio \
  --codes knowledge/client_codes/synthetic_test.yaml \
  --pretty

# Eval harness (checks source + archetype per account)
python evals/run_portfolio_eval.py
```

Without `--docs-root`, unique cases still classify via client codes; ambiguous/missing become `unresolved`. Offline proof of both paths (mocked LLM): `pytest tests/test_portfolio_offline.py -q`.

Officer-code → archetype mappings live in `knowledge/client_codes/` (not under fixtures). Use `synthetic_test.yaml` with the sample portfolio fixtures; keep `default.yaml` for non-synthetic / production-ish manuals.



## Prerequisites



Requires Ollama with models from `.env`:



- `OLLAMA_MODEL_OCR` (olmocr2) — reads every page

- `OLLAMA_MODEL` (qwen2.5) — structured extraction / classification

