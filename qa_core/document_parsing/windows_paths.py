"""Windows Paddle C++ paths need an ASCII runtime cache; source weights stay intact."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from qa_core.utils import IngestionError, file_sha256


def ascii_runtime_root() -> Path:
    root = Path(os.getenv("OCR_ASCII_CACHE_ROOT", str(Path(tempfile.gettempdir()) / "market-regulation-ocr")))
    if os.name == "nt" and not str(root).isascii():
        raise IngestionError("Windows Paddle 需要 ASCII 缓存路径，请设置 OCR_ASCII_CACHE_ROOT。")
    root.mkdir(parents=True, exist_ok=True)
    return root


def paddle_model_path(source: Path) -> Path:
    if os.name != "nt" or str(source).isascii():
        return source
    files = sorted(file for file in source.rglob("*") if file.is_file())
    signature_data = [(file.relative_to(source).as_posix(), file.stat().st_size, file.stat().st_mtime_ns) for file in files]
    signature = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
    root = ascii_runtime_root()
    target = root / "models" / signature[:16] / source.name
    marker = target / ".source-signature"
    if marker.is_file() and marker.read_text(encoding="ascii") == signature and all(
        (target / relative).is_file() and (target / relative).stat().st_size == size
        for relative, size, _ in signature_data
    ):
        return target
    needed = sum(size for _, size, _ in signature_data)
    if shutil.disk_usage(root).free < needed + 100 * 1024 * 1024:
        raise IngestionError("ASCII 模型缓存空间不足，请调整 OCR_ASCII_CACHE_ROOT。")
    target.mkdir(parents=True, exist_ok=True)
    for file in files:
        destination = target / file.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.is_file() or file_sha256(destination) != file_sha256(file):
            temporary = destination.with_name(destination.name + ".copying")
            shutil.copy2(file, temporary)
            if file_sha256(file) != file_sha256(temporary):
                raise IngestionError("Windows 模型缓存复制校验失败。")
            temporary.replace(destination)
    marker.write_text(signature, encoding="ascii")
    return target

