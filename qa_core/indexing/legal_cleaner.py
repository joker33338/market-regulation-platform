"""Conservative cleanup: retain numbering, punctuation and paragraph evidence."""
from __future__ import annotations

from qa_core.indexing.models import SourceLine


def clean_lines(lines: list[SourceLine]) -> tuple[list[SourceLine], dict]:
    cleaned = []
    changes = 0
    for item in lines:
        text = item.text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").strip()
        changes += int(text != item.text)
        cleaned.append(SourceLine(text, item.page, item.line, item.new_paragraph, item.bbox))
    return cleaned, {"cleaner": "conservative-v1", "trimmed_lines": changes}

