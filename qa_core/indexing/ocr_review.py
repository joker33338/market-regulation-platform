"""Explicit review metadata; recognition status is never inferred from body text."""
from __future__ import annotations

import json
from pathlib import Path

from qa_core.utils import IngestionError, file_sha256


def review_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".review.json")


def read_review(path: Path) -> dict:
    sidecar = review_path(path)
    if not sidecar.exists():
        if path.name.lower().endswith("_ocr.md"):
            raise IngestionError("OCR 候选稿尚未复核，请先执行 review-ocr。")
        return {}
    value = json.loads(sidecar.read_text(encoding="utf-8"))
    if value.get("status") != "approved" or value.get("reviewed_sha256") != file_sha256(path):
        raise IngestionError("OCR 复核记录未通过或正文已改变，请重新复核。")
    if not value.get("reviewer"):
        raise IngestionError("OCR 复核记录缺少复核人。")
    return value

