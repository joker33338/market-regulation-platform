"""解析文本及表格表示的最小规范化。

原始识别文本由结果对象单独保留；清理值仅统一换行等格式，不推断或改写
法律内容。表格同时保留 HTML、网格和单元格跨度，避免 Markdown 丢失结构。"""
from __future__ import annotations

import html
from html.parser import HTMLParser

from .schemas import TableResult


def normalize_text(raw: str) -> str:
    """统一 CRLF、CR 换行为 LF，移除起始 BOM、行末及整体边界空白。

    返回清理后的副本；不改写行内字符、标点或识别错误。调用方须另外保留
    原始识别值，不能把格式规范化当作人工纠错。"""
    return "\n".join(line.rstrip() for line in raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").split("\n")).strip()


class _TableHTML(HTMLParser):
    """把 HTML 单元格解析为锚点坐标和跨度，并跟踪跨行占位。

    row、column 从 0 开始；occupied 防止后续行的单元格落入跨行合并区域。
    单元格跨度被限制在 1 到 1000，非法跨度回退为 1；只收集文本和 br 换行，
    不执行 HTML 内容。"""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells = []
        self.row = -1
        self.column = 0
        self.occupied = set()
        self.current = None

    def handle_starttag(self, tag, attrs):
        """遇到行标签推进逻辑行，遇到单元格标签跳过已被跨行占用的列并建立锚点。"""
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
        """仅将当前单元格内的数据追加到其正文，不拼接表格外的文本。"""
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag):
        """关闭单元格时保存锚点并登记其覆盖的网格，供下一行定位时跳过。"""
        if tag in {"td", "th"} and self.current is not None:
            cell = self.current
            self.cells.append(cell)
            for row in range(cell["row"], cell["row"] + cell["rowspan"]):
                for col in range(cell["column"], cell["column"] + cell["colspan"]):
                    self.occupied.add((row, col))
            self.column += cell["colspan"]
            self.current = None


def table_from_html(value: str, table_id: str, bbox=None, source=None) -> TableResult:
    """由 HTML 构建 TableResult，同时保留原 HTML、二维文本行及单元格跨度。

    网格超过十万格时不分配二维数组，仅保留 HTML 和人工检查警告。普通表格
    生成经过分隔符转义的 Markdown；含合并单元格时直接保留 HTML，避免丢失
    rowspan、colspan。bbox 与 source 由调用方提供，不凭文本推测来源坐标。"""
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
    """把二维值转换为转义后的 HTML，再复用统一表格解析逻辑。

    None 转为空字符串，其余值转文本；HTML 特殊字符经转义，避免内容被误当
    标签。仅有二维行值时不推断原文件中的合并单元格。"""
    rows = [[str(value) if value is not None else "" for value in row] for row in rows]
    markup = "<table>" + "".join("<tr>" + "".join("<td>" + html.escape(value) + "</td>" for value in row) +
                                 "</tr>" for row in rows) + "</table>"
    return table_from_html(markup, table_id, bbox, source)

