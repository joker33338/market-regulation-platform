"""Versioned JSON-safe contract shared by native parsing, OCR and structure."""
from __future__ import annotations

import dataclasses
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def json_safe(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {item.name: json_safe(getattr(value, item.name)) for item in dataclasses.fields(value)}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "tolist"):
        return json_safe(value.tolist())
    if hasattr(value, "item"):
        return json_safe(value.item())
    raise TypeError("Unsupported parsing output type: " + type(value).__name__)


@dataclass
class LayoutBlock:
    block_id: str
    kind: str
    raw_text: str
    bbox: list | None = None
    confidence: float | None = None
    reading_order: int = 0
    source_location: dict = field(default_factory=dict)


@dataclass
class TableResult:
    table_id: str
    html: str = ""
    markdown: str = ""
    rows: list[list[str]] = field(default_factory=list)
    cells: list[dict] = field(default_factory=list)
    bbox: list | None = None
    source_location: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PageResult:
    page_number: int
    parsing_method: str
    raw_text: str = ""
    normalized_text: str = ""
    markdown_content: str = ""
    layout_blocks: list[LayoutBlock] = field(default_factory=list)
    tables: list[TableResult] = field(default_factory=list)
    confidence: float | None = None
    source_location: dict = field(default_factory=dict)
    processing_time: float = 0.0
    parsing_status: str = "success"
    error_message: str | None = None
    error_type: str | None = None
    warnings: list[str] = field(default_factory=list)
    raw_result: dict = field(default_factory=dict)
    model_load_time: float = 0.0
    network_blocked_attempts: int = 0
    peak_memory_bytes: int | None = None


@dataclass
class DocumentResult:
    document_id: str
    file_name: str
    file_type: str
    source_location: dict
    pages: list[PageResult] = field(default_factory=list)
    processing_time: float = 0.0
    parsing_status: str = "success"
    error_message: str | None = None
    quality: dict = field(default_factory=dict)
    schema_version: str = "document-parsing-v1"
    requires_review: bool = False

    @classmethod
    def from_dict(cls, payload: dict) -> "DocumentResult":
        """Restore a persisted result, retaining page order, tables and provenance."""
        def values(model, item):
            return {field.name: item[field.name] for field in dataclasses.fields(model) if field.name in item}
        pages = []
        for item in payload.get("pages", []):
            page = values(PageResult, item)
            page["layout_blocks"] = [LayoutBlock(**values(LayoutBlock, block)) for block in item.get("layout_blocks", [])]
            page["tables"] = [TableResult(**values(TableResult, table)) for table in item.get("tables", [])]
            pages.append(PageResult(**page))
        document = values(cls, payload)
        document["pages"] = pages
        return cls(**document)

    @property
    def raw_text(self) -> str:
        return "\n\f\n".join(page.raw_text for page in self.pages)

    @property
    def markdown_content(self) -> str:
        return "\n\n".join(f"<!-- source-page: {page.page_number} -->\n\n{page.markdown_content}" for page in self.pages)

    def to_dict(self) -> dict:
        return {**json_safe(self), "raw_text": self.raw_text, "markdown_content": self.markdown_content}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)

