"""Small transport objects keep the offline pipeline free of web dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceLine:
    text: str
    page: int = 1
    line: int = 1
    new_paragraph: bool = True
    bbox: list[float] | None = None


@dataclass
class LegalUnit:
    text: str
    paragraph_no: int
    item_no: str | None = None
    spans: list[dict] = field(default_factory=list)


@dataclass
class Article:
    article_no: str
    chapter: str
    section: str
    part: str
    units: list[LegalUnit] = field(default_factory=list)

    @property
    def text(self) -> str:
        return self.article_no + " " + "\n".join(unit.text for unit in self.units)


@dataclass
class LegalDocument:
    law_name: str
    source_hash: str
    source_path: str
    lines: list[SourceLine]
    law_id: str | None = None
    metadata: dict = field(default_factory=dict)
    articles: list[Article] | None = None


@dataclass
class Chunk:
    chunk_id: str
    law_name: str
    chapter: str
    article_no: str
    seq: int
    content: str
    embedding_text: str
    input_hash: str
    metadata: dict
    embedding: list[float] | None = None

