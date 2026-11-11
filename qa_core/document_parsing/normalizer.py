"""No rewriting: keep recognized text and cleaned text as separate values."""
from __future__ import annotations

import html
from html.parser import HTMLParser

from .schemas import TableResult


def normalize_text(raw: str) -> str:
    return "\n".join(line.rstrip() for line in raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").split("\n")).strip()


class _TableHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells = []
        self.row = -1
        self.column = 0
        self.occupied = set()
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row += 1
            self.column = 0
        elif tag in {"td", "th"}:
            attrs = dict(attrs)
            if self.row < 0:
                self.row = 0
            while (self.row, self.column) in self.occupied:
                self.column += 1
            try:
                rowspan = max(1, min(int(attrs.get("rowspan", 1)), 1000))
                colspan = max(1, min(int(attrs.get("colspan", 1)), 1000))
            except (ValueError, TypeError):
                rowspan = colspan = 1
            self.current = {"row": self.row, "column": self.column, "rowspan": rowspan,
                            "colspan": colspan, "text": "", "header": tag == "th"}
        elif tag == "br" and self.current is not None:
            self.current["text"] += "\n"

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.current is not None:
            cell = self.current
            self.cells.append(cell)
            for row in range(cell["row"], cell["row"] + cell["rowspan"]):
                for col in range(cell["column"], cell["column"] + cell["colspan"]):
                    self.occupied.add((row, col))
            self.column += cell["colspan"]
            self.current = None


def table_from_html(value: str, table_id: str, bbox=None, source=None) -> TableResult:
    parser = _TableHTML()
    parser.feed(value)
    height = max((cell["row"] + cell["rowspan"] for cell in parser.cells), default=0)
    width = max((cell["column"] + cell["colspan"] for cell in parser.cells), default=0)
    if height * width > 100_000:
        return TableResult(table_id, html=value, bbox=bbox, source_location=source or {},
                           warnings=["表格网格过大，仅保留 HTML，需人工检查。"])
    rows = [[""] * width for _ in range(height)]
    for cell in parser.cells:
        rows[cell["row"]][cell["column"]] = cell["text"]
    # 存在合并单元格时以 HTML 为结构依据，避免 Markdown 丢失跨度。
    merged = any(cell["rowspan"] != 1 or cell["colspan"] != 1 for cell in parser.cells)
    if rows and not merged:
        safe = lambda text: text.replace("|", r"\|").replace("\n", "<br>")
        markdown = "\n".join(["| " + " | ".join(map(safe, rows[0])) + " |",
                              "| " + " | ".join(["---"] * width) + " |"] +
                             ["| " + " | ".join(map(safe, row)) + " |" for row in rows[1:]])
    else:
        markdown = value
    return TableResult(table_id, value, markdown, rows, parser.cells, bbox, source or {},
                       ["含合并单元格，Markdown 保留 HTML。"] if merged else [])


def table_from_rows(rows: list[list], table_id: str, bbox=None, source=None) -> TableResult:
    rows = [[str(value) if value is not None else "" for value in row] for row in rows]
    markup = "<table>" + "".join("<tr>" + "".join("<td>" + html.escape(value) + "</td>" for value in row) +
                                 "</tr>" for row in rows) + "</table>"
    return table_from_html(markup, table_id, bbox, source)

