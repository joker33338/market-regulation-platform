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


def _docx_table_html(element) -> tuple[str, list[str]]:
    """按 OOXML 网格追踪相邻行的合并锚点，再交给现有 HTML 标准化。"""
    rows, anchors, warnings = [], [], []
    active = {}
    for row_number, row in enumerate(element.findall(W + "tr")):
        before = row.find(W + "trPr/" + W + "gridBefore")
        column = int(before.get(W + "val", "0")) if before is not None else 0
        if not 0 <= column <= 1000:
            raise IngestionError("DOCX 表格省略列数超过资源上限。")
        current, next_active = [], {}
        for cell in row.findall(W + "tc"):
            text = "\n".join("".join(node.text or "" for node in paragraph.iter(W + "t"))
                             for paragraph in cell.findall(W + "p"))
            span = cell.find(W + "tcPr/" + W + "gridSpan")
            merge = cell.find(W + "tcPr/" + W + "vMerge")
            colspan = max(1, int(span.get(W + "val", "1"))) if span is not None else 1
            if colspan > 1000:
                raise IngestionError("DOCX 表格列跨度超过资源上限。")
            key = (column, colspan)
            state = merge.get(W + "val", "continue") if merge is not None else None
            if state == "continue" and key in active:
                anchor = active[key]
                anchor["rowspan"] += 1
                if text:
                    # 非空延续格也不能丢字；原 XML 另行完整保留供核对。
                    anchor["text"] += ("\n" if anchor["text"] else "") + text
                    warnings.append("DOCX 纵向合并延续格含正文，已保留至锚点，需人工检查。")
                next_active[key] = anchor
            else:
                anchor = {"row": row_number, "column": column, "rowspan": 1,
                          "colspan": colspan, "text": text}
                current.append(anchor)
                anchors.append(anchor)
                if state == "restart":
                    next_active[key] = anchor
                elif state is not None:
                    warnings.append("DOCX 纵向合并标记没有匹配的上行锚点，已保留独立格及原 XML。")
            column += colspan
        rows.append(current)
        active = next_active

    markup = []
    for row_number, cells in enumerate(rows):
        occupied = {col for anchor in anchors
                    if anchor["row"] < row_number < anchor["row"] + anchor["rowspan"]
                    for col in range(anchor["column"], anchor["column"] + anchor["colspan"])}
        column, values = 0, []
        for cell in cells:
            # gridBefore 省略的网格位置须保留；跨行占位由 HTML rowspan 表达。
            while column < cell["column"]:
                if column not in occupied:
                    values.append("<td></td>")
                column += 1
            attrs = "".join(f' {key}="{cell[key]}"' for key in ("rowspan", "colspan") if cell[key] > 1)
            values.append("<td" + attrs + ">" + html.escape(cell["text"]).replace("\n", "<br>") + "</td>")
            column = cell["column"] + cell["colspan"]
        markup.append("<tr>" + "".join(values) + "</tr>")
    return "<table>" + "".join(markup) + "</table>", list(dict.fromkeys(warnings))


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
            markup, warnings = _docx_table_html(element)
            table = table_from_html(markup, str(len(tables)),
                                    source={**source, "body_index": index})
            table.warnings.extend(warnings)
            tables.append(table)
            markdown.append(table.markdown)
    raw = "\n".join(texts)
    return PageResult(1, "native_docx", raw, normalize_text(raw), "\n\n".join(markdown), blocks, tables,
                      source_location=source, warnings=["DOCX 页码为逻辑页；保留正文与表格原始顺序。"],
                      raw_result={"body_xml": ET.tostring(body, encoding="unicode")})

