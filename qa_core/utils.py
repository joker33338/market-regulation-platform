"""Deterministic identities, adapted from KnowForge qa_core/utils.py."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def stable_hash(*parts: object) -> str:
    # JSON framing avoids delimiter collisions between identity components.
    raw = json.dumps(parts, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class IngestionError(ValueError):
    """An actionable error safe to display without connection credentials."""

