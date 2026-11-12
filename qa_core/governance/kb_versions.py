"""Keep lifecycle operations separate from ingestion and online retrieval."""
from qa_core.storage.database import Database


def publish(database: Database, version: str, **guards) -> dict:
    database.publish(version, **guards)
    return {"version": version, "status": "ACTIVE", "action": "publish"}


def rollback(database: Database, version: str, **guards) -> dict:
    database.publish(version, rollback=True, **guards)
    return {"version": version, "status": "ACTIVE", "action": "rollback"}

