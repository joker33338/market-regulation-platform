"""Loaders adapted from KnowForge; preserve PDF pages and DOCX body order."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from qa_core.indexing.models import LegalDocument, SourceLine
from qa_core.indexing.ocr_review import read_review
from qa_core.utils import IngestionError, file_sha256

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf", ".docx"}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _text_lines(path: Path) -> list[SourceLine]:
    text = path.read_text(encoding="utf-8-sig")
    return [SourceLine(line, 1, index) for index, line in enumerate(text.splitlines(), 1)]


def _reviewed_ocr_lines(path: Path, review: dict) -> list[SourceLine]:
    result = []
    pages = path.read_text(encoding="utf-8-sig").split("\f")
    original_pages = review.get("pages", [])
    if len(pages) != len(original_pages):
        raise IngestionError("OCR 复核稿的分页与来源记录不一致，请保留分页符。")
    for page_no, page_text in enumerate(pages, 1):
        originals = original_pages[page_no - 1].get("lines", [])
        for index, line in enumerate(page_text.strip("\n").splitlines(), 1):
            original = originals[index - 1] if index <= len(originals) else {}
            bbox = original.get("bbox") if original.get("text") == line else None
            result.append(SourceLine(line, page_no, index, True, bbox))
    return result


def _docx_lines(path: Path) -> list[SourceLine]:
    with ZipFile(path) as archive:
        body = ET.fromstring(archive.read("word/document.xml")).find(W + "body")
    if body is None:
        return []
    result = []
    for element in body:
        if element.tag == W + "tbl":
            raise IngestionError("DOCX 含表格；MVP 请将附件表格另存为可核对的正文材料，避免静默丢失。")
        if element.tag != W + "p":
            continue
        parts = []
        for node in element.iter():
            if node.tag == W + "t":
                parts.append(node.text or "")
            elif node.tag in {W + "br", W + "cr"}:
                parts.append("\n")
            elif node.tag == W + "tab":
                parts.append("\t")
        paragraph = "".join(parts)
        for n, line in enumerate(paragraph.split("\n")):
            result.append(SourceLine(line, 1, len(result) + 1, n == 0))
    return result


def _pdf_lines(path: Path) -> list[SourceLine]:
    try:
        import fitz
    except ImportError as exc:
        raise IngestionError("读取 PDF 需要安装 requirements.txt 中的 PyMuPDF。") from exc
    result = []
    with fitz.open(path) as document:
        for page_no, page in enumerate(document, 1):
            blocks = page.get_text("blocks", sort=True)
            page_lines = []
            for block in blocks:
                if len(block) > 6 and block[6] != 0:
                    continue
                for index, line in enumerate(str(block[4]).splitlines()):
                    page_lines.append(SourceLine(line, page_no, len(page_lines) + 1, index == 0, list(block[:4])))
            if not any(line.text.strip() for line in page_lines):
                raise IngestionError(f"PDF 第 {page_no} 页没有文本层，需要先离线 OCR 并人工复核。")
            result.extend(page_lines)
    return result


def load_file(path: str | Path, *, law_name: str | None = None, law_id: str | None = None) -> LegalDocument:
    path = Path(path).resolve()
    review = read_review(path)
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise IngestionError("不支持的文件类型；MVP 支持 TXT、MD、PDF、DOCX。")
    if review.get("status") == "approved":
        lines = _reviewed_ocr_lines(path, review)
    elif path.suffix.lower() == ".docx":
        lines = _docx_lines(path)
    elif path.suffix.lower() == ".pdf":
        lines = _pdf_lines(path)
    else:
        lines = _text_lines(path)
    meaningful = [re.sub(r"^\s*#{1,6}\s*", "", line.text).strip() for line in lines if line.text.strip()]
    if not meaningful:
        raise IngestionError("文件没有可入库的文本。")
    first = meaningful[0]
    if law_name is None and not re.match(r"^第.+[条章节编]", first):
        law_name = first.strip("《》")
    return LegalDocument(
        law_name=law_name or path.stem, law_id=law_id,
        source_hash=file_sha256(path), source_path=str(path), lines=lines,
        metadata={"format": path.suffix.lower(), "review": review,
                  "paragraph_basis": "pdf_text_block" if path.suffix.lower() == ".pdf" else "source_paragraph"},
    )


def collect_files(path: str | Path) -> list[Path]:
    root = Path(path)
    if root.is_file():
        return [root]
    if not root.is_dir():
        raise IngestionError("输入文件或目录不存在。")
    files = sorted(item for item in root.rglob("*") if item.is_file() and item.suffix.lower() in SUPPORTED_SUFFIXES)
    if not files:
        raise IngestionError("目录内没有受支持的材料。")
    return files

