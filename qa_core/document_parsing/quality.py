"""Heuristic quality findings, never a legal correctness decision."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from qa_core.indexing.legal_structure import ARTICLE
from .schemas import DocumentResult

NUM = r"[〇零一二三四五六七八九十百千万两0-9]+"
ARTICLE_FIND = re.compile(rf"第\s*{NUM}\s*条(?:\s*之\s*{NUM})?")


@dataclass(frozen=True)
class RoutingThresholds:
    low_confidence: float = 0.8
    min_page_characters: int = 12
    max_invalid_ratio: float = 0.02

    def __post_init__(self):
        if not 0 <= self.low_confidence <= 1 or not 0 <= self.max_invalid_ratio <= 1 or self.min_page_characters < 0:
            raise ValueError("Invalid routing thresholds")


def assess_document(result: DocumentResult, low_confidence: float = 0.8, *, thresholds=None) -> dict:
    thresholds = thresholds or RoutingThresholds(low_confidence=low_confidence)
    low_confidence = thresholds.low_confidence
    findings = []
    occurrences = {}
    previous_article = False
    for page in result.pages:
        location = {"page_number": page.page_number}
        text = page.raw_text.strip()
        if not text:
            findings.append({"code": "empty_page", **location, "severity": "review"})
        elif len(text) < thresholds.min_page_characters:
            findings.append({"code": "short_page", **location, "severity": "review"})
        invalid = sum(char in "\ufffd\x00" for char in text) / max(len(text), 1)
        if invalid > thresholds.max_invalid_ratio:
            findings.append({"code": "invalid_character_ratio", **location, "severity": "review"})
        if page.source_location.get("complex_layout"):
            findings.append({"code": "complex_layout", **location, "severity": "info"})
        for year, month, day in re.findall(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", text):
            try:
                date(int(year), int(month), int(day))
            except ValueError:
                findings.append({"code": "invalid_date", **location, "severity": "review"})
        if re.search(r"(?:金额|价款|罚款)[^。\n]{0,16}(?:不确定|[?？�])|[0-9][?？�]+\s*元", text):
            findings.append({"code": "uncertain_amount", **location, "severity": "review"})
        if page.parsing_status == "failed":
            findings.append({"code": "page_failed", **location, "severity": "error"})
            previous_article = False
        if page.confidence is not None and page.confidence < low_confidence:
            findings.append({"code": "low_confidence", **location, "severity": "review"})
        if "\ufffd" in page.raw_text or "\x00" in page.raw_text:
            findings.append({"code": "invalid_characters", **location, "severity": "review"})
        labels = []
        for line in page.raw_text.splitlines():
            match = ARTICLE.match(line.strip())
            if match:
                label = re.sub(r"\s+", "", match.group(1))
                labels.append(label)
                occurrences.setdefault(label, []).append(page.page_number)
        if previous_article and page.raw_text.strip() and not labels:
            findings.append({"code": "possible_cross_page_article", **location, "severity": "review",
                             "message": "本页没有新条号，可能续接前页；未据此自动改写正文。"})
        elif previous_article and labels and not ARTICLE.match(page.raw_text.lstrip().splitlines()[0]):
            findings.append({"code": "possible_cross_page_article", **location, "severity": "review"})
        if labels:
            previous_article = True
        for table in page.tables:
            widths = {len(row) for row in table.rows}
            if len(widths) > 1 or table.warnings:
                findings.append({"code": "table_alignment_review", **location, "severity": "review",
                                 "table_id": table.table_id})
        if any(block.kind == "table" for block in page.layout_blocks) and not page.tables:
            findings.append({"code": "table_structure_missing", **location, "severity": "review"})
    for label, pages in occurrences.items():
        if len(pages) > 1:
            findings.append({"code": "duplicate_article_number", "article": label, "pages": pages, "severity": "review"})
    raw = result.raw_text
    if raw.strip() and not occurrences:
        findings.append({"code": "no_article_heading", "severity": "review",
                         "message": "可能是规范性文件、表格或条号漏识别；不能据此判断违法或解析必然错误。"})
    dates = re.findall(r"\d{4}年\s*\d{1,2}月\s*\d{1,2}日", raw)
    route_codes = {"page_failed", "empty_page", "short_page", "low_confidence", "invalid_character_ratio",
                   "table_structure_missing", "table_alignment_review"}
    reasons = sorted({item["code"] for item in findings if item["code"] in route_codes})
    if result.parsing_status in {"failed", "partial"}:
        reasons.append("engine_failed")
    confidences = [page.confidence for page in result.pages if page.confidence is not None]
    return {
        "routing": {"fallback_recommended": bool(reasons), "reasons": reasons,
                    "average_confidence": sum(confidences) / len(confidences) if confidences else None,
                    "thresholds": {"low_confidence": low_confidence, "min_page_characters": thresholds.min_page_characters,
                                   "max_invalid_ratio": thresholds.max_invalid_ratio}},
        "findings": findings, "article_headings": occurrences,
        "features": {
            "possible_law_names": re.findall(r"《[^》\n]{2,100}》", raw)[:30],
            "chapters": re.findall(rf"第\s*{NUM}\s*[编章节]", raw),
            "items": re.findall(rf"[（(]{NUM}[）)]", raw),
            "has_supplement": "附则" in raw,
            "legal_references": ARTICLE_FIND.findall(raw),
            "dates": dates, "has_effective_date_phrase": "施行" in raw or "生效" in raw,
            "has_revision_phrase": "修订" in raw or "修正" in raw,
            "table_count": sum(len(page.tables) for page in result.pages),
        },
        "review_required": bool(findings) or result.requires_review,
        "disclaimer": "启发式解析质量检查不能替代法律原文与效力审核；未声称条号完整性或法律正确性。",
    }

