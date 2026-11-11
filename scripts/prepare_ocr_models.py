"""Explicit, approved-only official model download; inference never invokes this."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qa_core.document_parsing.config import LAYOUT_MODEL, OCR_MODELS, TABLE_MODELS
from qa_core.config.settings import ROOT
from qa_core.utils import IngestionError, file_sha256

BASE = "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/"


def download(name: str, model_root: Path) -> dict:
    target = model_root / name
    if (target / "inference.pdiparams").is_file() and (target / "inference.yml").is_file():
        return {"name": name, "source_url": BASE + name + "_infer.tar", "reused": True}
    root = model_root.resolve()
    downloads = root / ".downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    archive_path = downloads / (name + "_infer.tar")
    url = BASE + name + "_infer.tar"
    with urllib.request.urlopen(url, timeout=120) as response, archive_path.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    archive_hash = file_sha256(archive_path)
    staging = downloads / (name + "-unpacked")
    staging.mkdir(exist_ok=False)
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            member_target = (staging / member.name).resolve()
            if not member_target.is_relative_to(staging.resolve()) or member.issym() or member.islnk():
                raise IngestionError("模型归档包含不安全路径或链接。")
        archive.extractall(staging, filter="data")
    configs = list(staging.rglob("inference.yml"))
    if len(configs) != 1:
        raise IngestionError("模型归档结构不符合预期。")
    source = configs[0].parent.resolve()
    if not source.is_relative_to(root) or not target.resolve().is_relative_to(root):
        raise IngestionError("模型移动目标超出项目模型目录。")
    if target.exists():
        raise IngestionError("模型目标已存在但不完整，请人工核查后重试。")
    shutil.move(str(source), str(target))
    # 清理前先解析路径，并确认位于专用下载目录内。
    if staging.resolve().is_relative_to(downloads.resolve()):
        shutil.rmtree(staging)
    archive_path.unlink()
    print(json.dumps({"downloaded": name}, ensure_ascii=False), flush=True)
    return {"name": name, "source_url": url, "archive_sha256": archive_hash, "reused": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", type=Path, default=ROOT / "models" / "ocr")
    parser.add_argument("--include-tables", action="store_true")
    args = parser.parse_args()
    names = list(OCR_MODELS) + [LAYOUT_MODEL]
    if args.include_tables:
        names += list(TABLE_MODELS)
    args.model_root.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        models = list(pool.map(lambda name: download(name, args.model_root), names))
    for model in models:
        directory = args.model_root / model["name"]
        model["files"] = [{"path": file.relative_to(directory).as_posix(), "bytes": file.stat().st_size,
                           "sha256": file_sha256(file)} for file in sorted(directory.rglob("*")) if file.is_file()]
    manifest = {"source": "PaddlePaddle official BOS inference models", "models": models,
                "paddleocr": "3.3.2", "paddlex": "3.3.10", "paddlepaddle": "3.2.2",
                "license_note": "See docs/ocr-integration/06-离线部署说明.md; preserve upstream notices."}
    (args.model_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"models": len(models), "total_bytes": sum(
        file["bytes"] for model in models for file in model["files"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()

