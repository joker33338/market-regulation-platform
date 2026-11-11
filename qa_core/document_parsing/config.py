from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from qa_core.config.settings import ROOT
from qa_core.utils import IngestionError

OCR_MODELS = ("PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec")
LAYOUT_MODEL = "PP-DocLayout-M"
TABLE_MODELS = (
    "PP-LCNet_x1_0_table_cls", "SLANeXt_wired", "SLANet_plus",
    "RT-DETR-L_wired_table_cell_det", "RT-DETR-L_wireless_table_cell_det",
)


class ParsingSafetyError(IngestionError):
    """不可通过换引擎绕过的本地资源拒绝，保留安全机器码。"""
    MESSAGES = {"image_pixel_limit": "图片像素数超过配置上限。",
                "file_byte_limit": "文件大小超过配置上限。",
                "pdf_page_limit": "PDF 页数超过配置上限。",
                "docx_expanded_limit": "DOCX 解压后超过资源上限。"}

    def __init__(self, code):
        self.code = code
        super().__init__(self.MESSAGES[code])


def validate_image_safety(path: Path, config):
    from PIL import Image
    try:
        with Image.open(path) as image:
            if image.width * image.height > config.max_image_pixels:
                raise ParsingSafetyError("image_pixel_limit")
    except Image.DecompressionBombError as exc:
        raise ParsingSafetyError("image_pixel_limit") from exc


def validate_input_safety(path: Path, config):
    """复用缓存也必须接受当前原文件的硬限额，不加载 OCR、不改变文件。"""
    if path.stat().st_size > config.max_file_bytes:
        raise ParsingSafetyError('file_byte_limit')
    if path.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
        validate_image_safety(path, config)
    elif path.suffix.lower() == '.pdf':
        import fitz
        with fitz.open(path) as document:
            if not document.is_pdf or document.needs_pass:
                raise IngestionError('缓存源 PDF 无效或无法读取。')
            if len(document) > config.max_pages:
                raise ParsingSafetyError('pdf_page_limit')
    elif path.suffix.lower() == '.docx':
        from zipfile import ZipFile
        with ZipFile(path) as archive:
            if sum(info.file_size for info in archive.infolist()) > config.max_file_bytes:
                raise ParsingSafetyError('docx_expanded_limit')


@dataclass(frozen=True)
class ParsingConfig:
    model_root: Path = ROOT / "models" / "ocr"
    device: str = "cpu"
    offline: bool = True
    cpu_threads: int = 4
    dpi: int = 160
    enable_tables: bool = False
    max_file_bytes: int = 100 * 1024 * 1024
    max_pages: int = 200
    max_image_pixels: int = 20_000_000
    max_image_side: int = 2400
    max_files: int = 20
    min_pdf_text_chars: int = 24
    low_confidence: float = 0.8
    worker_timeout: int = 300

    def __post_init__(self):
        if self.device != "cpu":
            raise IngestionError("当前集成验收范围为 CPU；未启用未经验证的 GPU 配置。")
        if not self.offline:
            raise IngestionError("解析服务只允许离线模型；联网下载请单独运行模型准备脚本。")
        if not 72 <= self.dpi <= 300 or self.cpu_threads < 1:
            raise IngestionError("DPI 应在 72–300 范围，cpu_threads 应大于 0。")
        if min(self.max_pages, self.max_file_bytes, self.max_image_pixels, self.max_files, self.worker_timeout) <= 0:
            raise IngestionError("解析资源限额必须大于 0。")

    @classmethod
    def from_env(cls) -> "ParsingConfig":
        root = Path(os.getenv("OCR_MODEL_ROOT", str(ROOT / "models" / "ocr")))
        return cls(model_root=root if root.is_absolute() else ROOT / root,
                   device=os.getenv("OCR_DEVICE", "cpu"),
                   cpu_threads=int(os.getenv("OCR_CPU_THREADS", "4")),
                   dpi=int(os.getenv("OCR_DPI", "160")),
                   enable_tables=os.getenv("OCR_ENABLE_TABLES", "0") == "1")

    def required_models(self, method: str) -> tuple[str, ...]:
        names = OCR_MODELS
        if method == "structure":
            names += (LAYOUT_MODEL,)
            if self.enable_tables:
                names += TABLE_MODELS
        return names

    def validate_models(self, method: str) -> dict[str, Path]:
        paths = {}
        missing = []
        for name in self.required_models(method):
            path = self.model_root / name
            if not (path / "inference.pdiparams").is_file() or not (path / "inference.yml").is_file() or not any(
                (path / file).is_file() for file in ("inference.json", "inference.pdmodel")
            ):
                missing.append(name)
            paths[name] = path
        if missing:
            raise IngestionError("缺少完整本地模型：" + "、".join(missing) +
                                 "。请显式运行 scripts/prepare_ocr_models.py；解析时不会下载。")
        return paths

