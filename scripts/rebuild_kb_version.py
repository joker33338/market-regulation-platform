"""KnowForge-style entry name, forwarding to the offline ingestion CLI."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.ingest_legal_documents import main

if __name__ == "__main__":
    raise SystemExit(main(["ingest", *sys.argv[1:]]))

