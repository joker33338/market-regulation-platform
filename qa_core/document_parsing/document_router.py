"""Unified local-file entry. Native, OCR and structure are chosen page by page."""
from __future__ import annotations

import logging
import math
import re
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from qa_core.config.settings import ROOT
from qa_core.utils import IngestionError, file_sha256
from .config import ParsingConfig, ParsingSafetyError, validate_image_safety
from .diagnostics import attached_diagnostic
from .native import docx_document, pdf_page
from .normalizer import normalize_text
from .paddle_ocr import PaddleOCRService
from .paddle_structure import PaddleStructureService
from .quality import assess_document
from .runtime import PaddleRuntime
from .schemas import DocumentResult, LayoutBlock, PageResult

logger = logging.getLogger(__name__)
SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".txt", ".md"}


def looks_multicolumn(page) -> bool:
    blocks = [block for block in page.get_text("blocks") if len(block) < 7 or block[6] == 0]
    for index, left in enumerate(blocks):
        for right in blocks[index + 1:]:
            overlap = min(left[3], right[3]) - max(left[1], right[1])
            height = min(left[3] - left[1], right[3] - right[1])
            separated = left[2] < right[0] or right[2] < left[0]
            if separated and height > 0 and overlap / height > 0.4 and abs(left[0] - right[0]) > page.rect.width * 0.25:
                return True
    return False


def has_vector_grid(page) -> bool:
    """Detect ruled PDF layouts even when cells are empty and no table is extracted."""
    horizontal = vertical = 0
    for drawing in page.get_drawings():
        for item in drawing.get('items', []):
            if item[0] != 'l':
                continue
            start, end = item[1:3]
            horizontal += abs(start.y - end.y) < 1 and abs(start.x - end.x) > 30
            vertical += abs(start.x - end.x) < 1 and abs(start.y - end.y) > 30
    return horizontal >= 2 and vertical >= 2


def has_hidden_text_layer(page) -> bool:
    """Detect an existing invisible OCR layer, rather than visible PDF text."""
    traces = page.get_texttrace()
    total = sum(len(span.get("chars", [])) for span in traces)
    hidden = sum(len(span.get("chars", [])) for span in traces if span.get("type") == 3)
    return total > 0 and hidden / total >= 0.8


def has_text_table_hint(page) -> bool:
    """Aligned text is a routing hint, never a replacement for verified cells."""
    for table in page.find_tables(strategy="text").tables:
        rows = [[str(cell or "").strip() for cell in row] for row in table.extract()]
        rows = [row for row in rows if sum(bool(cell) for cell in row) >= 2]
        if len(rows) < 3 or table.col_count < 2:
            continue
        numeric_rows = sum(any(re.search(r"\d", cell) for cell in row) for row in rows[1:])
        if numeric_rows >= max(2, math.ceil((len(rows) - 1) / 2)):
            return True
    return False


def has_grid(image_path: Path) -> bool:
    """A routing hint, not a claim that all table layouts can be detected."""
    try:
        import cv2
        import numpy as np
        # OpenCV's Windows file reader does not reliably accept Unicode paths.
        payload = image_path.read_bytes()
        image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_GRAYSCALE) if payload else None
        if image is None:
            return False
        mask = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        height, width = mask.shape
        horizontal = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, width // 5), 1)))
        vertical = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(30, height // 5))))
        return int((horizontal.sum(axis=1) > width * 255 * 0.3).sum()) > 5 and int(
            (vertical.sum(axis=0) > height * 255 * 0.3).sum()) > 5
    except (ImportError, OSError):
        return False


class DocumentParser:
    def __init__(self, config: ParsingConfig | None = None, *, runtime=None):
        self.config = config or ParsingConfig.from_env()
        self.runtime = runtime or PaddleRuntime(self.config)
        self.ocr = PaddleOCRService(self.runtime)
        self.structure = PaddleStructureService(self.runtime, self.config.enable_tables)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.runtime.close()

    def _check_path(self, path: str | Path) -> Path:
        if str(path).lower().startswith(("http://", "https://")):
            raise IngestionError("只允许本地文件，不接收远程文档 URL。")
        path = Path(path).resolve()
        if not path.is_file():
            raise IngestionError("输入文件不存在。")
        if path.suffix.lower() not in SUPPORTED:
            raise IngestionError("不支持该文件格式；支持 PDF、JPG、JPEG、PNG、DOCX、TXT、MD。")
        if path.stat().st_size > self.config.max_file_bytes:
            raise ParsingSafetyError("file_byte_limit")
        return path

    def _infer(self, method: str, image: Path, page_number: int, source: dict) -> PageResult:
        service = self.structure if method == "structure" else self.ocr
        return service.parse_image(str(image), page_number, source)

    def parse(self, path: str | Path, mode: str = "auto", *, page_numbers: list[int] | None = None) -> DocumentResult:
        started = time.perf_counter()
        if mode not in {"auto", "ocr", "structure"}:
            raise IngestionError("mode 必须是 auto、ocr 或 structure。")
        path = self._check_path(path)
        if page_numbers is not None and (path.suffix.lower() != ".pdf" or not page_numbers):
            raise IngestionError("指定页码仅支持 PDF，且页码列表不能为空。")
        digest = file_sha256(path)
        source = {"file_path": str(path), "file_sha256": digest}
        result = DocumentResult(digest, path.name, path.suffix.lower(), source)
        if path.suffix.lower() == ".docx":
            if mode != "auto":
                raise IngestionError("Word 使用原生解析，不能强制 OCR；请先显式转换为 PDF 或图片。")
            try:
                result.pages = [docx_document(path, {**source, "coordinate_space": "docx_body",
                                                   "page_number_basis": "logical"}, self.config.max_file_bytes)]
            except Exception as exc:
                result.pages = [self._error_page(1, "native_docx", source, exc)]
        elif path.suffix.lower() in {".txt", ".md"}:
            if mode != "auto":
                raise IngestionError("文本材料不调用 OCR，请使用 auto。")
            raw = path.read_text(encoding="utf-8-sig")
            blocks = [LayoutBlock(str(index), "text", text, reading_order=index,
                                  source_location={**source, "line": index + 1})
                      for index, text in enumerate(raw.splitlines())]
            normalized = normalize_text(raw)
            result.pages = [PageResult(1, "native_text", raw, normalized, raw, blocks, source_location=source,
                                      parsing_status="success" if normalized.strip() else "needs_review",
                                      warnings=[] if normalized.strip() else ["文本没有可提取的正文，请核对原始文件。"])]
        elif path.suffix.lower() == ".pdf":
            self._parse_pdf(path, mode, result, source, page_numbers)
        else:
            with tempfile.TemporaryDirectory(prefix="market-ocr-") as directory:
                image, image_source = self._prepare_image(path, Path(directory), source)
                method = "structure" if mode == "structure" or (mode == "auto" and has_grid(image)) else "ocr"
                try:
                    result.pages = [self._infer(method, image, 1, image_source)]
                except Exception as exc:
                    result.pages = [self._error_page(1, method, image_source, exc)]
        if result.pages:
            failed = sum(page.parsing_status == "failed" for page in result.pages)
            result.parsing_status = "failed" if failed == len(result.pages) else ("partial" if failed else "success")
        else:
            result.parsing_status = "failed"
            result.error_message = "文档没有可解析页面。"
        result.requires_review = any(page.parsing_method in {"ocr", "structure"} or page.warnings for page in result.pages)
        if (result.file_type == ".pdf" and result.parsing_status == "success"
                and not any(page.raw_text.strip() or any(
                    cell.get("text", "").strip() for table in page.tables for cell in table.cells
                ) for page in result.pages)):
            # 合法空白页仍可留在混合文档中；整份无正文不能报解析成功。
            result.parsing_status = "needs_review"
            result.requires_review = True
            result.error_message = "PDF 没有可提取的正文，请核对原始文件。"
        result.processing_time = time.perf_counter() - started
        result.quality = assess_document(result, self.config.low_confidence)
        result.requires_review = result.requires_review or result.quality["review_required"]
        if any(page.parsing_status == "needs_review" for page in result.pages) and result.parsing_status == "success":
            result.parsing_status = "needs_review"
        logger.info("Parsed document=%s pages=%d status=%s elapsed=%.3f",
                    digest[:12], len(result.pages), result.parsing_status, result.processing_time)
        return result

    def _prepare_image(self, path: Path, directory: Path, source: dict):
        from PIL import Image, ImageOps
        validate_image_safety(path, self.config)
        with Image.open(path) as image:
            if image.width * image.height > self.config.max_image_pixels:
                raise ParsingSafetyError("image_pixel_limit")
            original = image.size
            prepared = ImageOps.exif_transpose(image).convert("RGB")
            prepared.thumbnail((self.config.max_image_side, self.config.max_image_side))
            target = directory / "input.png"
            prepared.save(target)
            return target, {**source, "coordinate_space": "raster_pixel",
                            "image_size": list(prepared.size), "original_image_size": list(original)}

    def _parse_pdf(self, path: Path, mode: str, result: DocumentResult, source: dict,
                   page_numbers: list[int] | None = None):
        import fitz
        with fitz.open(path) as pdf:
            if not pdf.is_pdf:
                raise IngestionError("文件内容不是 PDF，与扩展名不符。")
            if pdf.needs_pass:
                raise IngestionError("PDF 已加密，需要先提供可读取的本地副本。")
            if len(pdf) > self.config.max_pages:
                raise ParsingSafetyError("pdf_page_limit")
            if page_numbers is not None:
                if any(number < 1 or number > len(pdf) for number in page_numbers):
                    raise IngestionError("指定页码超出 PDF 页数范围。")
                result.source_location["selected_pages"] = sorted(set(page_numbers))
            for page_no, page in enumerate(pdf, 1):
                if page_numbers is not None and page_no not in page_numbers:
                    continue
                page_started = time.perf_counter()
                page_source = {**source, "page_number": page_no, "coordinate_space": "pdf_point",
                               "page_size": [page.rect.width, page.rect.height]}
                method = mode
                replaced_text_layer = False
                native_candidate = None
                try:
                    raw = page.get_text("text")
                    image_rects = [item["bbox"] for item in page.get_image_info()]
                    area = max(page.rect.width * page.rect.height, 1)
                    image_fraction = max(((box[2] - box[0]) * (box[3] - box[1]) / area for box in image_rects), default=0)
                    if mode == "auto":
                        page_source["complex_layout"] = looks_multicolumn(page) or has_vector_grid(page)
                        # A header on a scanned page must not suppress OCR of its image body.
                        text_length = len("".join(raw.split()))
                        scanned = text_length == 0 or (bool(image_rects) and (
                            text_length < self.config.min_pdf_text_chars or (image_fraction > 0.65 and (
                                text_length < 120 or has_hidden_text_layer(page)))))
                        replaced_text_layer = scanned and bool(raw.strip()) and has_hidden_text_layer(page)
                        if not raw.strip() and not image_rects and not page.get_drawings():
                            result.pages.append(PageResult(page_no, "native_pdf", source_location=page_source,
                                                           warnings=["空白页，未加载 OCR。"]))
                            continue
                        if not scanned:
                            native = pdf_page(page, page_no, page_source)
                            if native.raw_text.strip():
                                native_candidate = native
                            text_table_hint = (self.config.enable_tables and not native.tables
                                               and has_text_table_hint(page))
                            if text_table_hint:
                                page_source["text_table_hint"] = True
                                page_source["complex_layout"] = True
                                native.source_location.update(page_source)
                            native.source_location["complex_layout"] = bool(native.tables) or page_source["complex_layout"]
                            if native.tables or (not looks_multicolumn(page) and not text_table_hint):
                                native.processing_time = time.perf_counter() - page_started
                                result.pages.append(native)
                                continue
                            method = "structure"
                        else:
                            method = "ocr"
                    with tempfile.TemporaryDirectory(prefix="market-ocr-page-") as directory:
                        scale = min(self.config.dpi / 72, self.config.max_image_side / max(page.rect.width, page.rect.height),
                                    math.sqrt(self.config.max_image_pixels / area))
                        image = Path(directory) / "page.png"
                        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                        pixmap.save(image)
                        inference_source = {**page_source, "coordinate_space": "raster_pixel",
                                            "image_size": [pixmap.width, pixmap.height],
                                            "pdf_scale_x": pixmap.width / page.rect.width,
                                            "pdf_scale_y": pixmap.height / page.rect.height}
                        del pixmap
                        if mode == "auto" and method == "ocr" and has_grid(image):
                            method = "structure"
                        parsed = self._infer(method, image, page_no, inference_source)
                        if replaced_text_layer:
                            parsed.raw_result["pdf_text_layer"] = raw
                            parsed.warnings.append("检测到扫描件的隐藏文字层，已重新识别；原文字层保留供核对。")
                        parsed.processing_time = time.perf_counter() - page_started
                        result.pages.append(parsed)
                        logger.info("Parsed page=%s/%s method=%s status=%s elapsed=%.2fs", page_no, len(pdf),
                                    parsed.parsing_method, parsed.parsing_status, parsed.processing_time)
                except Exception as exc:
                    failed = self._error_page(page_no, method, page_source, exc)
                    failed.processing_time = time.perf_counter() - page_started
                    if native_candidate is not None:
                        # 增强失败不应清空本页已成功提取的原生候选，也不能取消人工复核。
                        retained = replace(
                            native_candidate, parsing_status="needs_review",
                            warnings=[*native_candidate.warnings, "版面增强失败，已保留原生候选；阅读顺序和表格结构须人工复核。"],
                            error_type=failed.error_type, error_message=failed.error_message,
                            processing_time=failed.processing_time,
                            raw_result={**native_candidate.raw_result, **failed.raw_result, "enhancement_failure": {
                                "attempted_method": method, "error_type": failed.error_type,
                                "error_message": failed.error_message, "retained_method": "native_pdf"}},
                        )
                        result.pages.append(retained)
                    else:
                        result.pages.append(failed)

    @staticmethod
    def _error_page(number: int, method: str, source: dict, error: Exception) -> PageResult:
        logger.warning("Parsing page %s failed: %s", number, type(error).__name__)
        message = str(error) if isinstance(error, IngestionError) else "解析失败：" + type(error).__name__
        diagnostic = attached_diagnostic(error, component='paddle') if method in {'ocr', 'structure'} else None
        if diagnostic:
            message = "本地解析引擎无法加载，请查看安全诊断与本地运行日志。"
        return PageResult(number, method, source_location=source, parsing_status="failed",
                          error_message=message, error_type=type(error).__name__,
                          raw_result={'engine_availability': diagnostic} if diagnostic else {})

    def parse_batch(self, paths: list[Path], mode: str = "auto", *,
                    page_numbers: list[int] | None = None) -> list[DocumentResult]:
        if len(paths) > self.config.max_files:
            raise IngestionError("本批文件数超过配置上限。")
        results = []
        for path in paths:
            try:
                results.append(self.parse(path, mode, page_numbers=page_numbers))
            except Exception as exc:
                error = str(exc) if isinstance(exc, IngestionError) else "解析失败：" + type(exc).__name__
                from qa_core.utils import stable_hash
                results.append(DocumentResult(stable_hash(str(Path(path).resolve())), Path(path).name,
                                              Path(path).suffix, {"file_path": str(Path(path).resolve())},
                                              parsing_status="failed", error_message=error,
                                              requires_review=True,
                                              quality={"safety_rejection": {"status": "SAFE_REJECT", "code": exc.code}}
                                              if isinstance(exc, ParsingSafetyError) else {}))
        return results


def export_result(result: DocumentResult, output_root: str | Path) -> dict:
    """Names are generated from a hash, never from an untrusted file name."""
    from qa_core.utils import stable_hash
    directory = Path(output_root) / (result.document_id or stable_hash(result.file_name, result.error_message))
    directory.mkdir(parents=True, exist_ok=True)
    from .export_assets import export_images
    images = export_images(result, directory)
    result_path = directory / "document.json"
    markdown_path = directory / "document.md"
    result_path.write_text(result.to_json(), encoding="utf-8")
    markdown_path.write_text(result.markdown_content, encoding="utf-8")
    for page in result.pages:
        (directory / f"raw-page-{page.page_number:04d}.json").write_text(
            __import__("json").dumps(page.raw_result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return {"json": str(result_path), "markdown": str(markdown_path), "images": images}

