"""本地解析与性能记录入口，不调用上传接口、向量模型或数据库写入。"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import sys
import threading
import time
from dataclasses import replace
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qa_core.document_parsing.config import ParsingConfig
from qa_core.document_parsing.document_router import DocumentParser, SUPPORTED, export_result
from qa_core.utils import IngestionError


class MemorySampler:
    def __init__(self):
        self.peak = None
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        try:
            import psutil
        except ImportError:
            return
        def sample():
            process = psutil.Process()
            self.peak = 0
            while not self._stop.wait(0.1):
                try:
                    memory = process.memory_info().rss + sum(child.memory_info().rss for child in process.children(recursive=True))
                    self.peak = max(self.peak, memory)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        self._thread = threading.Thread(target=sample, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()


def main(argv=None):
    parser = argparse.ArgumentParser(description="本地法律文档解析及真实性能记录")
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--mode", choices=["auto", "ocr", "structure"], default="auto")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-root", type=Path)
    parser.add_argument("--tables", action="store_true", help="仅本次启用表格；未指定时继承进程配置。")
    parser.add_argument("--dpi", type=int, default=160)
    parser.add_argument("--cpu-threads", type=int, default=4)
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--pages", type=int, nargs="+", help="仅重测指定 PDF 页码，保留原始页码。")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING"], default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(name)s: %(message)s")
    config = ParsingConfig.from_env()
    config = replace(config, enable_tables=config.enable_tables or args.tables, dpi=args.dpi,
                     cpu_threads=args.cpu_threads, max_pages=args.max_pages)
    if args.model_root:
        config = replace(config, model_root=args.model_root.resolve())
    inputs = []
    for path in args.input:
        inputs.extend(sorted(item for item in path.iterdir() if item.suffix.lower() in SUPPORTED and item.is_file())
                      if path.is_dir() else [path])
    sampler = MemorySampler()
    sampler.start()
    started = time.perf_counter()
    try:
        with DocumentParser(config) as service:
            results = service.parse_batch(inputs, args.mode, page_numbers=args.pages)
        exports = [export_result(result, args.output_dir) for result in results]
        sampler.stop()
        versions = {}
        for name in ["paddleocr", "paddlex", "paddlepaddle", "PyMuPDF", "numpy"]:
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = None
        report = {
            "mode": args.mode, "tables": config.enable_tables, "offline_guard": True, "device": config.device,
            "selected_pages": args.pages, "dpi": config.dpi, "cpu_threads": config.cpu_threads,
            "elapsed_seconds": time.perf_counter() - started, "sampled_peak_total_rss_bytes": sampler.peak,
            "files": len(results), "failed_files": sum(result.parsing_status in {"failed", "partial"} for result in results),
            "pages": sum(len(result.pages) for result in results),
            "failed_pages": sum(page.parsing_status == "failed" for result in results for page in result.pages),
            "review_pages": sum(page.parsing_status == "needs_review" or bool(page.warnings)
                                or (page.confidence is not None and page.confidence < config.low_confidence)
                                for result in results for page in result.pages),
            "empty_text_pages": [page.page_number for result in results for page in result.pages
                                 if not page.raw_text.strip()],
            "table_count": sum(len(page.tables) for result in results for page in result.pages),
            "method_counts": dict(Counter(page.parsing_method for result in results for page in result.pages)),
            "environment": versions,
            "documents": [{"file_name": result.file_name, "status": result.parsing_status,
                           "processing_time": result.processing_time,
                           "page_metrics": [{"page": page.page_number, "method": page.parsing_method,
                              "status": page.parsing_status, "seconds": page.processing_time,
                              "load_seconds": page.model_load_time, "confidence": page.confidence,
                              "blocks": len(page.layout_blocks), "tables": len(page.tables),
                              "network_blocked_attempts": page.network_blocked_attempts,
                              "text_chars": len(page.raw_text), "warnings": page.warnings,
                              "error_type": page.error_type, "error_message": page.error_message}
                              for page in result.pages], "exports": export}
                          for result, export in zip(results, exports, strict=True)],
            "accuracy": None, "accuracy_note": "未提供人工逐字金标，不能报告识别准确率。",
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report["failed_files"] else 0
    except IngestionError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        sampler.stop()


if __name__ == "__main__":
    raise SystemExit(main())

