"""Materialize Paddle's image references from the original local page."""
from __future__ import annotations

import re
from pathlib import Path

from qa_core.utils import IngestionError, file_sha256

IMAGE_REF = re.compile(r"imgs/img_in_[A-Za-z_]+_box_(\d+)_(\d+)_(\d+)_(\d+)\.jpg")


def export_images(result, directory: Path) -> list[str]:
    """Keep photo/seal crops usable after temporary inference files disappear."""
    assets = []
    source_path = Path(result.source_location.get("file_path", ""))
    verified = False
    for page in result.pages:
        references = page.source_location.get("export_images")
        if references is None:
            references = []
            for match in IMAGE_REF.finditer(page.markdown_content):
                if any(item["source_ref"] == match.group() for item in references):
                    continue
                references.append({"source_ref": match.group(), "bbox": list(map(int, match.groups())),
                                   "relative_path": f"images/page-{page.page_number:04d}-{len(references)+1:02d}.png"})
        if not references:
            continue
        if not verified:
            if not source_path.is_file() or file_sha256(source_path) != result.document_id:
                raise IngestionError("图片导出的源文件不存在或内容已变化，请使用同一原件重测。")
            verified = True
        for index, item in enumerate(references, 1):
            # 输出路径由程序生成，禁止把模型文本直接用作文件路径。
            relative = f"images/page-{page.page_number:04d}-{index:02d}.png"
            target = directory / relative
            target.parent.mkdir(exist_ok=True)
            x1, y1, x2, y2 = item["bbox"]
            if not (0 <= x1 < x2 and 0 <= y1 < y2):
                raise IngestionError("图片区域坐标无效，未导出错位图片。")
            if source_path.suffix.lower() == ".pdf":
                import fitz
                sx = page.source_location.get("pdf_scale_x")
                sy = page.source_location.get("pdf_scale_y")
                if not sx or not sy:
                    raise IngestionError("图片导出缺少 PDF 坐标比例。")
                with fitz.open(source_path) as pdf:
                    original = pdf[page.page_number - 1]
                    clip = fitz.Rect(x1 / sx, y1 / sy, x2 / sx, y2 / sy) & original.rect
                    if clip.is_empty:
                        raise IngestionError("图片区域位于原页范围外。")
                    original.get_pixmap(matrix=fitz.Matrix(sx, sy), clip=clip, alpha=False).save(target)
            else:
                from PIL import Image, ImageOps
                with Image.open(source_path) as original:
                    prepared = ImageOps.exif_transpose(original).convert("RGB")
                    size = page.source_location.get("image_size")
                    if not size:
                        raise IngestionError("图片导出缺少原识别图像尺寸。")
                    prepared = prepared.resize(tuple(size))
                    prepared.crop((x1, y1, x2, y2)).save(target)
            page.markdown_content = page.markdown_content.replace(item["source_ref"], relative)
            item["relative_path"] = relative
            assets.append(str(target))
        page.source_location["export_images"] = references
    return assets
