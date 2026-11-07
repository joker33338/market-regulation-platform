# Round 01 cases

Source: `f2a5c925f0305a2e7df21f750b20bed63db40de3`.

| Case | Evidence | Result |
| --- | --- | --- |
| Inventory/hash/size/PDF pages/image verification | `tests/round01_probe.py`; 135 files verified | PASS |
| Real JPG + scanned PDF first page OCR | `tests/round01_ocr_smoke.py`; S00001/S00002 | PASS execution only |
| Real local BGE dimension | `tests/round01_bge_smoke.py`; 1024 | PASS |
| Native PDF/DOCX/table order/merged cells/JSON export | `tests/test_document_parsing.py`, `test_optional_loaders.py`; synthetic fixtures | PASS |
| Legal hierarchy, cleaning, bounded chunks, parent ID/spans | `tests/test_mvp.py`; synthetic fixtures | PASS |
| Hash duplicates, incremental vector reuse, rollback, SQLite retrieval | `tests/test_mvp.py`; synthetic fixtures | PASS |
| Empty and whitespace TXT | `test_round01_regressions.py::Round01Regressions` | FAIL DOC-001 |
| Unicode grid-image path, decoded-image positive control | same regression module | FAIL OCR-001 |
| Oversize/parser batch limits, corrupt-file batch handling | existing document parser tests | PASS synthetic |
| MinerU reference lifecycle and faults | `tests/test_mineru_contract.py` | PASS 13 tests; not product acceptance |
| Production MinerU adapter/config switch | explicitly skipped test; client absent | BLOCKED |
| FastAPI upload/auth/ownership | no actual routes at baseline | BLOCKED |
| PostgreSQL/pgvector live transaction, write, retrieval | existing opt-in integration skipped | BLOCKED |
| Remote MinerU Standard inference/Aliyun deployment/GPU | no approved remote endpoint or deployment | NOT_TESTED |
| Corpus-wide OCR, complex table ground truth, character/amount accuracy | no labeled reference; bounded smoke only | NOT_TESTED |
| Real process kill/recovery; real PP-StructureV3 inference | existing fixtures do not prove actual engine behavior | NOT_TESTED |

Run `python -B -m unittest tests.test_round01_regressions -v` for 3 expected failures at baseline, and `python -B -m unittest tests.test_mineru_contract -v` for contract fixtures. All fixtures contain synthetic text only. Future pytest runner can collect unittest tests without changing their assertions; pytest is currently unavailable and was not installed.

## Fix regression update — 2026-11-07

Baseline expectations above are historical. On Fix `f7c4d75e1ff11e2d06d75f44336bf4b89f96aa57`, the original bug reproducers now PASS. `tests/test_round01_fix_acceptance.py` adds four QA cases: Windows original-artifact retention FAIL, corrupt-local-file sibling isolation FAIL, simulated DB failure visibility PASS, simulated DB failure retry without new remote task PASS. Use `tests/run_round01_validation.py --source <isolated-fix-checkout>` to select the actual code under test. Full combined execution and feature statuses are in 06/05 reports.
