"""Offline PaddleOCR adapter, adapted from KnowForge. Models must exist locally."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from qa_core.indexing.ocr_review import review_path
from qa_core.utils import IngestionError, file_sha256

SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def create_ocr_engine(det_model: Path, rec_model: Path, cls_model: Path, rec_dict: Path):
    for path in [det_model, rec_model, cls_model]:
        if not path.is_dir() or not any(path.glob("*.pdmodel")) or not any(path.glob("*.pdiparams")):
            raise IngestionError("需要完整的本地 PaddleOCR 2.x 推理模型目录；不会自动下载。")
    if not rec_dict.is_file():
        raise IngestionError("OCR 字典文件不存在。")
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise IngestionError("OCR 可选依赖未安装；需要 paddleocr 2.9.1 及匹配的 Paddle CPU 运行时。") from exc
    return PaddleOCR(det_model_dir=str(det_model), rec_model_dir=str(rec_model),
                     cls_model_dir=str(cls_model), rec_char_dict_path=str(rec_dict),
                     use_angle_cls=True, lang="ch", use_gpu=False, show_log=False)


def recognize_file(path: Path, output_dir: Path, engine) -> dict:
    if path.suffix.lower() not in SUPPORTED:
        raise IngestionError("不支持此 OCR 文件类型。")
    digest = file_sha256(path)
    directory = output_dir / digest[:16]
    directory.mkdir(parents=True, exist_ok=True)
    images = []
    if path.suffix.lower() == ".pdf":
        import fitz
        with fitz.open(path) as pdf:
            for index, page in enumerate(pdf, 1):
                image = directory / f"page-{index}.png"
                page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False).save(image)
                images.append(image)
    else:
        images = [path]
    pages = []
    for number, image in enumerate(images, 1):
        raw = engine.ocr(str(image), cls=True)
        page_lines = raw[0] if raw and len(raw) == 1 else raw
        lines = []
        for item in page_lines or []:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                payload = item[1]
                if isinstance(payload, (list, tuple)) and len(payload) >= 2:
                    lines.append({"text": str(payload[0]), "confidence": float(payload[1]), "bbox": item[0]})
        pages.append({"page": number, "lines": lines})
    if not any(page["lines"] for page in pages):
        raise IngestionError("OCR 未识别出文本。")
    candidate = directory / (path.stem + "_ocr.md")
    # 法律正文不插入工具生成的标题，页码及坐标另存复核记录。
    candidate.write_text("\n\f\n".join("\n".join(line["text"] for line in page["lines"]) for page in pages),
                         encoding="utf-8")
    sidecar = {"status": "pending", "source_sha256": digest, "source_path": str(path.resolve()),
               "candidate_sha256": file_sha256(candidate), "pages": pages}
    review_path(candidate).write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"candidate": str(candidate), "pages": len(pages), "status": "pending"}


def approve_candidate(path: Path, reviewer: str) -> dict:
    if not reviewer.strip():
        raise IngestionError("复核人不能为空。")
    sidecar_path = review_path(path)
    if not sidecar_path.is_file():
        raise IngestionError("没有 OCR 来源和复核记录，不能直接标记通过。")
    value = json.loads(sidecar_path.read_text(encoding="utf-8"))
    if not value.get("source_sha256") or not value.get("pages"):
        raise IngestionError("OCR 来源记录不完整。")
    value.update(status="approved", reviewer=reviewer.strip(),
                 reviewed_at=datetime.now(timezone.utc).isoformat(), reviewed_sha256=file_sha256(path))
    sidecar_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"candidate": str(path), "status": "approved", "reviewer": reviewer}

