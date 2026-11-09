"""Explicit reviewed-result to existing SQLite KB adapter; never publishes automatically."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qa_core.config.settings import Settings
from qa_core.document_parsing.schemas import DocumentResult
from qa_core.document_parsing.mineru_artifacts import reviewed_legal_document
from qa_core.indexing.service import ingest_documents
from qa_core.retrieval.models import create_embeddings
from qa_core.storage.database import Database


def main():
    parser = argparse.ArgumentParser(description="Review and stage a normalized parser result in an explicit SQLite KB")
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--law-name", required=True)
    parser.add_argument("--law-id")
    parser.add_argument("--version", required=True)
    parser.add_argument("--backend", choices=["local", "demo"], default="local")
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("Initialize a separate SQLite KB explicitly before staging results.")
    result = DocumentResult.from_dict(json.loads(args.result.read_text(encoding="utf-8")))
    document = reviewed_legal_document(result, reviewer=args.reviewer, law_name=args.law_name, law_id=args.law_id)
    settings = Settings.from_env()
    if args.backend == "demo":
        settings = replace(settings, embedding_backend="demo", embedding_dimension=32)
    embeddings = create_embeddings(settings)
    database = Database(sqlite_path=args.database)
    try:
        outcome = ingest_documents([document], database=database, embeddings=embeddings, settings=settings, version=args.version)
        print(json.dumps(outcome))
    finally:
        database.close()


if __name__ == "__main__":
    main()
