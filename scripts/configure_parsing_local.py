"""Create ignored local runtime configuration; print no credentials."""
import argparse
import json
import os
from pathlib import Path
import secrets


def main():
    import psycopg2
    from psycopg2.extensions import make_dsn
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-env", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("local/parsing-runtime.json"))
    args = parser.parse_args()
    values = {}
    for line in args.database_env.read_text(encoding="utf-8-sig").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    password = values.get("DOCKER_DB_PASSWORD")
    if not password or not os.getenv("MINERU_API_KEY"):
        raise ValueError("Explicit local database credentials and MinerU process credential required")
    dsn = make_dsn(host="127.0.0.1", port=15432, dbname="market_regulation", user="market_app", password=password)
    connection = psycopg2.connect(dsn, connect_timeout=5)
    try:
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('document_review.documents'),to_regclass('document_review.pages')")
            if not all(cursor.fetchone()):
                raise ValueError("Required existing document_review tables are missing; no migration applied")
    finally:
        connection.close()
    token = secrets.token_urlsafe(32)
    if args.output.is_file():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        existing = json.loads(previous.get("PARSING_API_TOKENS_JSON", "{}"))
        token = next(iter(existing), token)
    configuration = {"MINERU_ENABLED": "1", "MINERU_MODE": "remote", "MINERU_PROVIDER": "official",
                     "MINERU_API_URL": "https://mineru.net/api", "MINERU_API_KEY": os.environ["MINERU_API_KEY"],
                     "MINERU_CLOUD_MODEL": "vlm", "MINERU_RESULT_DIR": "local/mineru-live",
                     "MINERU_POLL_INTERVAL": "2", "MINERU_MAX_POLLS": "150",
                     "PARSING_API_TOKENS_JSON": json.dumps({token: "local-user"}), "PARSING_RESULT_PG_DSN": dsn}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(configuration, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(args.output, 0o600)
    access_file = args.output.with_name("workbench-access-code.txt")
    access_file.write_text(token, encoding="utf-8")
    os.chmod(access_file, 0o600)
    print(json.dumps({"configured": True, "database_readonly_preflight": "PASS", "schema_changed": False}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"configured": False, "error_type": type(exc).__name__}))
        raise SystemExit(1)
