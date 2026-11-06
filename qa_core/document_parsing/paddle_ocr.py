"""PP-OCRv5 service with page-level provenance and untouched recognized text."""
from __future__ import annotations

from qa_core.utils import IngestionError
from .normalizer import normalize_text
from .schemas import LayoutBlock, PageResult


def unwrap(raw: dict) -> dict:
    return raw.get("res", raw)


def decorate_location(source: dict, bbox) -> dict:
    value = dict(source)
    if bbox is not None and source.get("pdf_scale_x") and source.get("pdf_scale_y"):
        sx, sy = source["pdf_scale_x"], source["pdf_scale_y"]
        if len(bbox) == 4 and not isinstance(bbox[0], (list, tuple)):
            value["pdf_bbox"] = [bbox[0] / sx, bbox[1] / sy, bbox[2] / sx, bbox[3] / sy]
        else:
            value["pdf_polygon"] = [[point[0] / sx, point[1] / sy] for point in bbox]
    return value


class PaddleOCRService:
    def __init__(self, runtime):
        self.runtime = runtime

    def parse_image(self, image_path: str, page_number: int, source: dict) -> PageResult:
        payload = self.runtime.predict("ocr", image_path)
        raw = unwrap(payload["raw"])
        texts, scores = raw.get("rec_texts", []), raw.get("rec_scores", [])
        boxes = raw.get("rec_polys", raw.get("dt_polys", []))
        if not (len(texts) == len(scores) == len(boxes)):
            raise IngestionError("OCR 文字、置信度和坐标数量不一致，拒绝错位输出。")
        blocks = [LayoutBlock(str(index), "text", text, box, float(score), index,
                              decorate_location(source, box))
                  for index, (text, score, box) in enumerate(zip(texts, scores, boxes, strict=True))]
        text = "\n".join(texts)
        return PageResult(
            page_number, "ocr", text, normalize_text(text), text, blocks,
            confidence=sum(scores) / len(scores) if scores else None,
            source_location=source, processing_time=payload["processing_time"],
            parsing_status="success" if texts else "needs_review",
            warnings=[] if texts else ["本页 OCR 没有识别到文字，请人工核对。"],
            raw_result=payload["raw"], model_load_time=payload["model_load_time"],
            network_blocked_attempts=payload["network_blocked_attempts"],
            peak_memory_bytes=payload["peak_memory_bytes"],
        )

