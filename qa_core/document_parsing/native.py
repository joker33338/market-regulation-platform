"""Reuse native extraction and preserve table structure without calling OCR."""
from __future__ import annotations

import html
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from qa_core.indexing.document_loaders import W, _docx_lines
from qa_core.utils import IngestionError
from .normalizer import normalize_text, table_from_html, table_from_rows
from .schemas import LayoutBlock, PageResult


def pdf_page(page, page_number: int, source: dict) -> PageResult:
    tables = []
    warnings = []
    if hasattr(page, "find_tables"):
        try:
            findings = page.find_tables()
            for index, table in enumerate(findings.tables):
                rows = table.extract()
                if len(rows) >= 2 and any(any(cell not in (None, "") for cell in row) for row in rows):
                    value = table_from_rows(rows, str(index), list(table.bbox), source)
                    for cell in value.cells:
                        try:
                            cell["bbox"] = list(table.rows[cell["row"]].cells[cell["column"]])
                        except (IndexError, TypeError):
                            pass
                    tables.append(value)
        except Exception as exc:
            warnings.append("原生表格提取失败：" + type(exc).__name__)
    blocks = []
    raw_blocks = page.get_text("dict", flags=0, sort=True)["blocks"]
    sizes = [span["size"] for block in raw_blocks if block.get("type") == 0
             for line in block.get("lines", []) for span in line.get("spans", [])]
    median = statistics.median(sizes) if sizes else 12
    for index, block in enumerate(raw_blocks):
        if block.get("type") != 0:
            continue
        bbox = list(block["bbox"])
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        if any(table.bbox[0] <= cx <= table.bbox[2] and table.bbox[1] <= cy <= table.bbox[3] for table in tables):
            continue
        text = "\n".join("".join(span["text"] for span in line["spans"]) for line in block.get("lines", []))
        size = max((span["size"] for line in block.get("lines", []) for span in line["spans"]), default=median)
        kind = "title" if size >= median * 1.3 else "text"
        blocks.append(LayoutBlock(str(index), kind, text, bbox, None, index, source))
    text_parts = [(block.bbox[1], block.raw_text) for block in blocks]
    text_parts += [(table.bbox[1], "\n".join("\t".join(row) for row in table.rows)) for table in tables]
    text = "\n\n".join(value for _, value in sorted(text_parts, key=lambda item: item[0]))
    markdown_parts = [(block.bbox[1], ("# " if block.kind == "title" else "") + block.raw_text) for block in blocks]
    markdown_parts += [(table.bbox[1], table.markdown) for table in tables]
    markdown = "\n\n".join(value for _, value in sorted(markdown_parts, key=lambda item: item[0]))
    return PageResult(page_number, "native_pdf", text, normalize_text(text), markdown, blocks, tables,
                      source_location=source, warnings=warnings,
                      raw_result={"text_blocks": raw_blocks, "tables": [table.rows for table in tables]})


def docx_document(path: Path, source: dict, max_bytes: int) -> PageResult:
    with ZipFile(path) as archive:
        if sum(info.file_size for info in archive.infolist()) > max_bytes:
            raise IngestionError("DOCX 解压后超过资源上限。")
        body = ET.fromstring(archive.read("word/document.xml")).find(W + "body")
    if body is None:
        raise IngestionError("DOCX 没有正文。")
    if not any(element.tag == W + "tbl" for element in body):
        lines = _docx_lines(path)
        blocks = [LayoutBlock(str(index), "text", line.text, reading_order=index,
                              source_location={**source, "paragraph_index": index + 1})
                  for index, line in enumerate(lines)]
        raw = "\n".join(line.text for line in lines)
        return PageResult(1, "native_docx", raw, normalize_text(raw), raw, blocks, source_location=source,
                          warnings=["DOCX 页码为逻辑页，未运行 Word 排版引擎。"])
    blocks, tables, markdown, texts = [], [], [], []
    for index, element in enumerate(body):
        if element.tag == W + "p":
            raw = "".join(node.text or "" for node in element.iter(W + "t"))
            blocks.append(LayoutBlock(str(index), "text", raw, reading_order=index,
                                      source_location={**source, "paragraph_index": index + 1}))
            texts.append(raw)
            markdown.append(raw)
        elif element.tag == W + "tbl":
            rows = []
            merged = False
            for row in element.findall(W + "tr"):
                cells = []
                for cell in row.findall(W + "tc"):
                    text = "\n".join("".join(node.text or "" for node in paragraph.iter(W + "t"))
                                     for paragraph in cell.findall(W + "p"))
                    span = cell.find(".//" + W + "gridSpan")
                    merge = cell.find(".//" + W + "vMerge")
                    colspan = int(span.get(W + "val", "1")) if span is not None else 1
                    merged = merged or merge is not None
                    cells.append("<td" + (f' colspan="{colspan}"' if colspan > 1 else "") + ">" +
                                 html.escape(text) + "</td>")
                rows.append("<tr>" + "".join(cells) + "</tr>")
            table = table_from_html("<table>" + "".join(rows) + "</table>", str(len(tables)),
                                    source={**source, "body_index": index})
            if merged:
                table.warnings.append("DOCX 包含纵向合并标记；原始 XML 保留，行合并需人工检查。")
            tables.append(table)
            markdown.append(table.markdown)
    raw = "\n".join(texts)
    return PageResult(1, "native_docx", raw, normalize_text(raw), "\n\n".join(markdown), blocks, tables,
                      source_location=source, warnings=["DOCX 页码为逻辑页；保留正文与表格原始顺序。"],
                      raw_result={"body_xml": ET.tostring(body, encoding="unicode")})

