# Round 01 QA baseline — 2026-11-06

Source under test: `f2a5c925f0305a2e7df21f750b20bed63db40de3`.
QA branch: `qa/round1`. Git confirmed separate main, QA and Fix worktrees; `fix/round1` shares this source baseline. No business source edited, dependencies installed, services started, database migrations applied, remote documents sent or pushes performed.

## Executed environment and source inspection

Python 3.12.16; PyMuPDF 1.26.7; PaddleOCR 3.3.2; PaddlePaddle 3.2.2; sentence-transformers 4.1.0; torch 2.7.1+cpu; openpyxl 3.1.5. httpx and psycopg2 imports available. FastAPI, pytest and python-docx absent. Absence of python-docx does not prevent the implemented XML DOCX loader. psycopg is absent but the code uses psycopg2, so this is not a driver defect.

| Area | Source evidence and findings |
| --- | --- |
| HTTP/upload/MinerU | No FastAPI/APIRouter/MinerU implementation found in tracked Python sources; CLI entries are `query.py`, `scripts/ingest_legal_documents.py`. New capability gap, not regression. |
| Parsing | `qa_core/document_parsing/document_router.py::DocumentParser` supports PDF/images/DOCX/TXT/MD; `native.py` handles PDF/DOCX. Excel/legacy DOC not supported at this entry. No Excel/Word corpus samples. |
| OCR/structure | `config.py::validate_models`, `runtime.py::PaddleRuntime`, `paddle_ocr.py`, `paddle_structure.py`. Required OCR and structure model files present. Actual OCR succeeded on two samples; PP-StructureV3 real inference NOT_TESTED. |
| Cleaning/structure | `indexing/legal_cleaner.py`, `legal_structure.py`, `chunking.py::split_articles`; article-first legal pipeline. General document ingestion needs explicit design; do not assume legal splitter fits arbitrary dossiers. |
| Parent-child and identity | `chunking.py` stores parent article ID/text and source spans; `service.py::prepare_document` generates document/chunk identity and hashes. Existing synthetic tests pass. |
| Embedding | `retrieval/models.py::LocalEmbeddings`; real local BGE smoke PASS: one synthetic input, one 1024-dimensional vector. No corpus content sent externally. |
| Database | `storage/database.py::Database` uses direct psycopg2/SQLite, not an ORM/pool. Explicit transaction context commits/rolls back; document versions, chunks and KB source associations exist. MinerU task/file metadata absent. Live PostgreSQL BLOCKED: no explicitly isolated test DSN. SQLite tests passed. |
| Errors/config | `utils.py::IngestionError`, `config/settings.py`, parsing `config.py`; worker logs remain ignored. No uploaded-file ownership authorization layer found. |
| Deployment | `Dockerfile` is CPU Python image with idle command; `compose.yaml` has local model mounts and DB healthchecks, no MinerU GPU service. No deployment claimed. |

## Corpus inventory (read-only, anonymous)

`tests/round01_probe.py` uses `Path(os.environ['MARKET_REGULATION_TEST_CORPUS'])`.

135 files: 126 JPG (93.33%), 9 PDF (6.67%); Word/Excel/other types: 0.
114,303,711 bytes total; largest 7,518,898 bytes. Size bins: below 1 MiB 119; 1–5 MiB 15; at least 5 MiB 1. Zero empty files. SHA-256 duplicate groups/excess copies: 0/0.
All 9 PDFs opened: 43 pages, 0 text-layer pages, 43 pages without extractable text; 9 scan candidates. Lack of text alone is not semantic proof of scanned content. All 126 images passed Pillow verify. No unreadable PDF/image found at container/header verification level; full visual quality and complex-table inventory NOT_TESTED.

Samples S00001 (JPG) and S00002 (PDF page 1) were parsed serially with local OCR: both status success, normalized character counts 174 and 137. These are execution outcomes, not measured recognition accuracy. Chinese amount accuracy, reading order and table completeness require human ground truth and remain NOT_TESTED. Full corpus OCR was deliberately not run.

## Test results

Original suite: 64 tests, 63 PASS, 1 skipped PostgreSQL test. Final suite: 83 tests, 77 PASS, 4 FAIL, 2 skipped (PostgreSQL and absent production MinerU adapter). 13 passing new MinerU reference tests, one passing all-business-module import test; four failing new regression/preflight tests represent three bugs. No previous test removed or weakened.

Initial default-temp attempt failed with Windows access errors. Re-run using ignored workspace temporary directory completed; this is environment evidence, not product failure. OCR initially blocked by non-ASCII runtime cache; explicit writable ASCII cache enabled successful inference. Chinese-path grid defect remains separately reproducible.

Commands: use configured local interpreter as `<python>`, set TEMP/TMP to a writable ignored directory; set an ASCII TEMP/TMP and OCR_ASCII_CACHE_ROOT for real Windows Paddle inference. Local model paths come from ignored shared configuration (see `scripts/start_agent_workspace.ps1`, do not launch another interactive agent just for tests).

```text
<python> -B -m unittest discover -s tests -v
<python> -B -m tests.round01_probe
<python> -B -m tests.round01_ocr_smoke
<python> -B -m tests.round01_bge_smoke
```

Detailed execution output is ignored under `local/round01/` and `reports/`; never commit raw OCR outputs, model/environment paths or corpus mappings.
