"""PP-StructureV3 service. Keep engine order, HTML cells and original JSON."""
from __future__ import annotations

from .normalizer import normalize_text, table_from_html
from .paddle_ocr import decorate_location, unwrap
from .schemas import LayoutBlock, PageResult


class PaddleStructureService:
    def __init__(self, runtime, enable_tables: bool):
        self.runtime = runtime
        self.enable_tables = enable_tables

    def parse_image(self, image_path: str, page_number: int, source: dict) -> PageResult:
        payload = self.runtime.predict("structure", image_path)
        raw = unwrap(payload["raw"])
        entries = raw.get("parsing_res_list", [])
        ordered = sorted(enumerate(entries), key=lambda pair: (
            pair[1].get("block_order") if pair[1].get("block_order") is not None else pair[0]))
        blocks = []
        for rank, (original_index, item) in enumerate(ordered):
            bbox = item.get("block_bbox", item.get("bbox"))
            blocks.append(LayoutBlock(
                str(item.get("block_id", original_index)), item.get("block_label", "unknown"),
                item.get("block_content", ""), bbox, item.get("confidence"), rank,
                decorate_location(source, bbox),
            ))
        tables = []
        for index, item in enumerate(raw.get("table_res_list", [])):
            markup = item.get("pred_html", item.get("html", ""))
            table_blocks = [block for block in blocks if block.kind == "table"]
            bbox = item.get("bbox", item.get("table_bbox"))
            if bbox is None:
                matches = [block for block in table_blocks if block.raw_text == markup]
                if len(matches) == 1:
                    bbox = matches[0].bbox
                elif len(table_blocks) == 1 and len(raw["table_res_list"]) == 1:
                    bbox = table_blocks[0].bbox
            table = table_from_html(markup, str(index), bbox, decorate_location(source, bbox))
            boxes = item.get("cell_box_list", [])
            if len(boxes) == len(table.cells):
                for cell, bbox in zip(table.cells, boxes, strict=True):
                    cell["bbox"] = bbox
                    cell["source_location"] = decorate_location(source, bbox)
            elif boxes:
                table.warnings.append("HTML 单元格数与识别框数量不一致，原始框保留在 raw_result。")
            tables.append(table)
        # HTML/Markdown 之外，也保留可检索的单元格文字。
        # 引擎的表格块包含原始识别 HTML，需保留供核对。
        text_parts = []
        for block in blocks:
            if block.kind == "table":
                table_text = table_from_html(block.raw_text, block.block_id)
                text_parts.append("\n".join("\t".join(row) for row in table_text.rows) or block.raw_text)
            else:
                text_parts.append(block.raw_text)
        text = "\n".join(text_parts)
        scores = raw.get("overall_ocr_res", {}).get("rec_scores", [])
        markdown = payload["markdown"] or "\n\n".join(block.raw_text for block in blocks)
        warnings = []
        if any(block.kind == "table" for block in blocks) and not tables:
            warnings.append("检测到表格版面但没有结构化单元格；请启用 --tables 或人工检查。")
        if not text.strip():
            warnings.append("本页未提取到可检索文字，可能为照片或图像证据，请对照原页核对。")
        return PageResult(
            page_number, "structure", text, normalize_text(text), markdown, blocks, tables,
            sum(scores) / len(scores) if scores else None, source, payload["processing_time"],
            "success" if blocks and text.strip() else "needs_review",
            warnings=warnings, raw_result=payload["raw"], model_load_time=payload["model_load_time"],
            network_blocked_attempts=payload["network_blocked_attempts"],
            peak_memory_bytes=payload["peak_memory_bytes"],
        )

