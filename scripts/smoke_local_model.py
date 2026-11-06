"""Run the copied real BGE model against an isolated local SQLite database."""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qa_core.config.settings import ROOT, Settings
from qa_core.indexing.document_loaders import load_file
from qa_core.indexing.service import ingest_documents
from qa_core.retrieval.models import LocalEmbeddings
from qa_core.storage.database import Database
from query import ask


def main():
    start = time.monotonic()
    database_path = ROOT / "reports" / ("local-bge-" + uuid4().hex[:8] + ".sqlite3")
    settings = Settings()
    embeddings = LocalEmbeddings(settings)
    database = Database(sqlite_path=database_path)
    try:
        database.initialize()
        document = load_file(ROOT / "scenarios/market_regulation/data/示例管理办法.txt")
        first = ingest_documents([document], database=database, embeddings=embeddings,
                                 settings=settings, version="local-bge-v1")
        database.publish("local-bge-v1")
        result = ask("哪些情形需要提交示例材料？", stream=False, database=database, embeddings=embeddings)
        assert result["hits"] and result["hits"][0]["article_no"] == "第二条"
        unchanged = ingest_documents([document], database=database, embeddings=embeddings,
                                     settings=settings, version="local-bge-v2")
        assert unchanged["chunks_embedded"] == 0
        row = database.one("SELECT embedding FROM mr_chunks LIMIT 1")
        vector = json.loads(row["embedding"])
        report = {
            "model": "copied-local-bge-m3", "dimension": len(vector),
            "norm": math.sqrt(sum(value * value for value in vector)),
            "database": str(database_path), "first_build": first, "unchanged_build": unchanged,
            "top_article": result["hits"][0]["article_no"], "citations": result["citations"],
            "elapsed_seconds": round(time.monotonic() - start, 2), "network": "offline-enforced",
        }
        (ROOT / "reports/local_model_smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                                             encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key != "citations"},
                         ensure_ascii=False, indent=2))
    finally:
        database.close()


if __name__ == "__main__":
    main()

