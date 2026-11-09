"""End-to-end local UI API -> official parser -> existing test PostgreSQL.

Uses a generated one-page PDF only. Never accepts a corpus path.
"""
import argparse
import json
from pathlib import Path
import time
from uuid import uuid4

from mineru_official_smoke import synthetic_pdf


def main():
    import httpx
    import psycopg2
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("local/parsing-runtime.json"))
    parser.add_argument("--port", type=int, default=8180)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    token = next(iter(json.loads(config["PARSING_API_TOKENS_JSON"])))
    headers = {"Authorization": "Bearer " + token}
    base = f"http://127.0.0.1:{args.port}"
    with httpx.Client(timeout=30, trust_env=False) as client:
        page = client.get(base)
        page.raise_for_status()
        assert "text/html" in page.headers["content-type"]
        response = client.post(base + "/api/parse/files", params={"file_name": "synthetic-smoke.pdf"},
                               content=synthetic_pdf(), headers=headers)
        response.raise_for_status()
        response = client.post(base + "/api/parse/tasks", json={"file_ids": [response.json()["file_id"]]},
                               headers={**headers, "Idempotency-Key": "smoke-" + uuid4().hex})
        response.raise_for_status()
        task_id = response.json()["task_id"]
        evidence_path = Path("reports/upload-database-smoke.json")
        evidence_path.write_text(json.dumps({"task_id": task_id, "status": "submitted"}), encoding="utf-8")
        previous = None
        for attempt in range(150):
            response = client.get(base + "/api/parse/tasks/" + task_id, headers=headers)
            response.raise_for_status()
            task = response.json()
            if task["status"] != previous:
                print(json.dumps({"task_id": task_id, "status": task["status"]}), flush=True)
                previous = task["status"]
            if task["status"] in {"completed", "partial", "failed", "timed_out", "canceled"}:
                break
            time.sleep(2)
        assert task["status"] == "completed", task.get("error")
        parse_id = task["files"][0]["database_parse_id"]
        assert parse_id
        result = client.get(base + "/api/parse/tasks/" + task_id + "/results", headers=headers)
        result.raise_for_status()
        assert len(result.json()["results"]) == 1
    connection = psycopg2.connect(config["PARSING_RESULT_PG_DSN"], connect_timeout=5)
    try:
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute("""SELECT document_id,length(raw_text),length(markdown_content),
                (SELECT COUNT(*) FROM document_review.pages p WHERE p.parse_id=d.parse_id),
                (SELECT COUNT(*) FROM document_review.blocks b WHERE b.parse_id=d.parse_id)
                FROM document_review.documents d WHERE parse_id=%s""", (parse_id,))
            row = cursor.fetchone()
            assert row and row[1] > 0 and row[2] > 0 and row[3] == 1 and row[4] > 0
        summary = {"status": "PASS", "task_id": task_id, "parse_id": parse_id,
                   "text_characters": row[1], "markdown_characters": row[2], "pages": row[3], "blocks": row[4],
                   "schema_changed": False, "source": "synthetic-one-page-pdf"}
        evidence_path.write_text(json.dumps(summary), encoding="utf-8")
        print(json.dumps(summary))
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error_type": type(exc).__name__}))
        raise SystemExit(1)
