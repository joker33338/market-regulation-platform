"""Verify local model files; optional source comparison proves a complete copy."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qa_core.config.settings import ROOT
from qa_core.utils import IngestionError, file_sha256


def verify_model(model_path: Path, source: Path | None = None) -> dict:
    if not model_path.is_dir():
        raise IngestionError("模型目录不存在。")
    files = sorted(item for item in model_path.rglob("*") if item.is_file())
    if not files:
        raise IngestionError("模型目录为空。")
    entries = []
    for item in files:
        relative = item.relative_to(model_path).as_posix()
        digest = file_sha256(item)
        if source:
            original = source / relative
            if not original.is_file() or original.stat().st_size != item.stat().st_size or file_sha256(original) != digest:
                raise IngestionError("模型复制校验失败。")
        entries.append({"path": relative, "bytes": item.stat().st_size, "sha256": digest})
    if source and {entry["path"] for entry in entries} != {
        item.relative_to(source).as_posix() for item in source.rglob("*") if item.is_file()
    }:
        raise IngestionError("源模型与目标模型文件集合不一致。")
    if not any(entry["path"] in {"pytorch_model.bin", "model.safetensors"} for entry in entries):
        raise IngestionError("模型缺少完整权重文件。")
    manifest = {"model": model_path.name, "verified_against_source": bool(source),
                "file_count": len(entries), "total_bytes": sum(entry["bytes"] for entry in entries), "files": entries}
    output = model_path.parent / "model_manifest.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {key: value for key, value in manifest.items() if key != "files"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, default=ROOT / "models" / "bge-m3")
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_model(args.model_path, args.source), ensure_ascii=False))


if __name__ == "__main__":
    main()

