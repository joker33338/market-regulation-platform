"""One lazy local Paddle worker; strict offline guard never affects the business process."""
from __future__ import annotations

import importlib.metadata
import json
import logging
import multiprocessing
import os
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path

from qa_core.config.settings import ROOT
from qa_core.utils import IngestionError
from .config import LAYOUT_MODEL, OCR_MODELS, ParsingConfig
from .paddle_compat import share_table_ocr_pipeline, skip_disabled_chart_model
from .schemas import json_safe
from .windows_paths import ascii_runtime_root, paddle_model_path

logger = logging.getLogger(__name__)
_ENGINES = {}
_OFFLINE_INSTALLED = False
_BLOCKED = 0
_LOGGING_CONFIGURED = False


def install_offline_guard():
    global _OFFLINE_INSTALLED
    if _OFFLINE_INSTALLED:
        return
    def audit(event, args):
        global _BLOCKED
        if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname"}:
            _BLOCKED += 1
            raise OSError("Document parsing worker: network is disabled.")
    sys.addaudithook(audit)
    _OFFLINE_INSTALLED = True


def _build_engine(method: str, config: ParsingConfig):
    paths = {name: paddle_model_path(path) for name, path in config.validate_models(method).items()}
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(ascii_runtime_root() / "paddlex")
    os.environ["OMP_NUM_THREADS"] = str(config.cpu_threads)
    os.environ["FLAGS_use_mkldnn"] = "0"
    install_offline_guard()
    for name, expected in [("paddleocr", "3.3.2"), ("paddlex", "3.3.10"), ("paddlepaddle", "3.2.2")]:
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            raise IngestionError("缺少 " + name + "；请按 requirements-ocr.txt 安装。") from None
        if actual != expected:
            raise IngestionError(name + " 版本不匹配：需要 " + expected + "，当前 " + actual)
    try:
        from paddleocr import PaddleOCR, PPStructureV3
    except Exception as exc:
        logger.exception("Paddle import failed in isolated worker")
        raise IngestionError("Paddle 运行时加载失败：" + type(exc).__name__ + "；请查看安装诊断报告。") from None
    options = {
        "device": config.device, "cpu_threads": config.cpu_threads, "enable_mkldnn": False,
        "text_detection_model_name": OCR_MODELS[0], "text_detection_model_dir": str(paths[OCR_MODELS[0]]),
        "text_recognition_model_name": OCR_MODELS[1], "text_recognition_model_dir": str(paths[OCR_MODELS[1]]),
        "use_doc_orientation_classify": False, "use_doc_unwarping": False,
        "use_textline_orientation": False, "text_recognition_batch_size": 1,
        "text_det_limit_side_len": 1280, "text_det_limit_type": "max",
        "text_rec_score_thresh": 0.0,
    }
    if method == "ocr":
        return PaddleOCR(**options)
    options.update(
        layout_detection_model_name=LAYOUT_MODEL, layout_detection_model_dir=str(paths[LAYOUT_MODEL]),
        use_region_detection=False, use_table_recognition=config.enable_tables,
        use_formula_recognition=False, use_chart_recognition=False, use_seal_recognition=False,
    )
    if config.enable_tables:
        for prefix, name in [
            ("table_classification", "PP-LCNet_x1_0_table_cls"),
            ("wired_table_structure_recognition", "SLANeXt_wired"),
            ("wireless_table_structure_recognition", "SLANet_plus"),
            ("wired_table_cells_detection", "RT-DETR-L_wired_table_cell_det"),
            ("wireless_table_cells_detection", "RT-DETR-L_wireless_table_cell_det"),
        ]:
            options[prefix + "_model_name"] = name
            options[prefix + "_model_dir"] = str(paths[name])
    with skip_disabled_chart_model():
        engine = PPStructureV3(**options)
    return share_table_ocr_pipeline(engine)


def _worker_predict(method: str, image_path: str, config: ParsingConfig) -> dict:
    global _LOGGING_CONFIGURED
    if not _LOGGING_CONFIGURED:
        log_path = ROOT / "reports" / "parsing_worker.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(process)d %(message)s"))
        logger.addHandler(handler)
        _LOGGING_CONFIGURED = True
    started = time.perf_counter()
    key = (method, config)
    load_time = 0.0
    try:
        if key not in _ENGINES:
            load_started = time.perf_counter()
            _ENGINES[key] = _build_engine(method, config)
            load_time = time.perf_counter() - load_started
        engine = _ENGINES[key]
        options = {"use_table_orientation_classify": False} if method == "structure" else {}
        result = next(iter(engine.predict(image_path, **options)), None)
        if result is None:
            raise IngestionError("Paddle 产线没有返回页面结果。")
        raw = result.json
        raw = raw() if callable(raw) else raw
        raw = json.loads(raw) if isinstance(raw, str) else json_safe(raw)
        markdown = ""
        if method == "structure":
            markdown_value = result.markdown
            markdown_value = markdown_value() if callable(markdown_value) else markdown_value
            markdown = markdown_value.get("markdown_texts", "") if isinstance(markdown_value, dict) else str(markdown_value)
        try:
            import psutil
            info = psutil.Process().memory_info()
            peak = getattr(info, "peak_wset", info.rss)
        except ImportError:
            peak = None
        return {"raw": raw, "markdown": markdown, "model_load_time": load_time,
                "processing_time": time.perf_counter() - started, "peak_memory_bytes": peak,
                "network_blocked_attempts": _BLOCKED}
    except IngestionError:
        raise
    except Exception as exc:
        logger.exception("Local Paddle %s failure", method)
        raise IngestionError("Paddle " + method + " 推理失败：" + type(exc).__name__ +
                             "；详细异常见 reports/parsing_worker.log。") from None


class PaddleRuntime:
    def __init__(self, config: ParsingConfig):
        self.config = config
        self._executor = None
        self._lock = threading.Lock()

    def predict(self, method: str, image_path: str) -> dict:
        self.config.validate_models(method)
        with self._lock:
            if self._executor is None:
                self._executor = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))
            try:
                return self._executor.submit(_worker_predict, method, image_path, self.config).result(
                    timeout=self.config.worker_timeout)
            except FutureTimeout:
                self.abort()
                raise IngestionError("Paddle 页面处理超时；当前解析器应关闭后重新创建。") from None

    def abort(self):
        if self._executor is not None:
            # Python 3.12 has no public terminate_workers API. Keep this small,
            # version-specific cleanup here so a timed-out predictor cannot leak.
            processes = list(getattr(self._executor, "_processes", {}).values())
            for process in processes:
                if process.is_alive():
                    process.terminate()
            for process in processes:
                process.join(timeout=5)
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    def close(self):
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None

