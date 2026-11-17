"""从同一原始文件重新导出 Paddle 识别结果引用的图片素材。

按页级坐标裁剪照片、印章等区域，避免推理临时文件清理后引用失效。导出前
验证原件摘要，输出文件名由程序生成，模型返回的路径不能直接作为写入位置。"""
from __future__ import annotations

import re
from pathlib import Path

from qa_core.utils import IngestionError, file_sha256

IMAGE_REF = re.compile(r"imgs/img_in_[A-Za-z_]+_box_(\d+)_(\d+)_(\d+)_(\d+)\.jpg")


def export_images(result, directory: Path) -> list[str]:
    """将识别结果中的图片引用物化到 directory 下，并返回导出文件路径列表。

    优先使用显式 export_images 元数据，否则从已知 Markdown 引用格式提取
    坐标并去重。首次真正导出时校验原件 SHA256 与文档身份一致。
    PDF 按记录的渲染比例还原页内裁剪框；图片按 EXIF 方向及识别尺寸恢复后
    裁剪。坐标、比例或原件不满足要求时拒绝导出。
    成功后同步更新页内 Markdown 引用和来源元数据；此函数有文件写入副作用，
    不是纯预览。此前已完成的导出文件不会因后续区域失败而自动回滚。"""
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
