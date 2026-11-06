"""Keep lifecycle operations separate from ingestion and online retrieval."""
from qa_core.storage.database import Database


def publish(database: Database, version: str) -> dict:
    database.publish(version)
    return {"version": version, "status": "ACTIVE", "action": "publish"}


def rollback(database: Database, version: str) -> dict:
    database.publish(version, rollback=True)
    return {"version": version, "status": "ACTIVE", "action": "rollback"}

