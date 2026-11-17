"""基于显式标题行提出拆分建议；按确认的字符范围保留原始来源。"""
from copy import deepcopy
import hashlib
import re

from pydantic import BaseModel, ConfigDict, Field

from qa_core.document_parsing.mineru_client import MinerUError


class SourceRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    expected_text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def text_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def suggest_segments(text):
    headings = []
    seen = set()
    offset = 0
    for line in text.splitlines(keepends=True):
        title = line.strip().strip("《》")
        if (2 <= len(title) <= 100
                and not re.match(r"^(依据|根据|按照|参照|违反|第[一二三四五六七八九十0-9]+[条章节款项])", title)
                and not re.search(r"[，。；;：:]", title)
                and re.search(r"(条例|办法|规定|细则|法|行政处罚决定书)$", title)):
            kind = "case" if title.endswith("行政处罚决定书") else "law"
            identity = title
            if kind == "case":
                following = text[offset:offset + 300]
                number = re.search(r"[^\n\f]{0,40}罚[^\n\f]{0,40}[〔\[]\d{4}[〕\]][^\n\f]{0,40}号", following)
                identity = title + (number.group(0).strip() if number else "")
            if identity not in seen:
                headings.append({"title": identity, "document_type": kind, "start": offset + len(line) - len(line.lstrip())})
                seen.add(identity)
        offset += len(line)
    if len(headings) < 2:
        return []
    signature = text_digest(text)
    for index, item in enumerate(headings):
        item.update(end=headings[index + 1]["start"] if index + 1 < len(headings) else len(text),
                    expected_text_sha256=signature, requires_confirmation=True)
        item["page_start"] = text.count("\f", 0, item["start"]) + 1
        item["page_end"] = text.count("\f", 0, max(item["start"], item["end"] - 1)) + 1
    return headings


def slice_result(result, source_range):
    value = source_range.model_dump() if isinstance(source_range, SourceRange) else source_range
    start, end = value["start"], value["end"]
    text = result.raw_text
    if (text_digest(text) != value["expected_text_sha256"] or
            not 0 <= start < end <= len(text)):
        raise MinerUError("source_scope_changed", 409)
    selected = deepcopy(result)
    selected.pages = []
    offset = 0
    for original in result.pages:
        page_end = offset + len(original.raw_text)
        left, right = max(start, offset), min(end, page_end)
        if left < right:
            if original.tables or any(block.kind == "table" for block in original.layout_blocks):
                raise MinerUError("source_scope_table_requires_review", 409)
            page = deepcopy(original)
            page.raw_text = original.raw_text[left - offset:right - offset]
            page.normalized_text = page.raw_text
            page.markdown_content = page.raw_text
            page.layout_blocks = []
            cursor = 0
            for block in original.layout_blocks:
                position = original.raw_text.find(block.raw_text, cursor)
                if position < 0:
                    raise MinerUError("source_scope_layout_mapping_required", 409)
                block_start, block_end = offset + position, offset + position + len(block.raw_text)
                begin, finish = max(left, block_start), min(right, block_end)
                cursor = position + len(block.raw_text)
                if begin < finish:
                    clipped = deepcopy(block)
                    clipped.raw_text = block.raw_text[begin - block_start:finish - block_start]
                    clipped.source_location = {**clipped.source_location,
                        "original_block_id": block.block_id, "original_page_number": original.page_number,
                        "source_text_start": begin, "source_text_end": finish, "source_scope": "source_text_scope_v1"}
                    page.layout_blocks.append(clipped)
            compact = lambda value: "".join(value.split())
            if compact(page.raw_text) != compact("".join(block.raw_text for block in page.layout_blocks)):
                raise MinerUError("source_scope_layout_mapping_required", 409)
            selected.pages.append(page)
        offset = page_end + 3
    if not selected.pages:
        raise MinerUError("source_scope_empty", 409)
    selected.quality["confirmed_source_range"] = value
    return selected
