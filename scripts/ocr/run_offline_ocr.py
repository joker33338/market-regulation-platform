"""Offline OCR candidate generation and explicit human review."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from qa_core.indexing.ocr_documents import approve_candidate, create_ocr_engine, recognize_file
from qa_core.utils import IngestionError


def main(argv=None):
    parser = argparse.ArgumentParser(description="离线 OCR，默认只生成待复核稿")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("recognize")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    for name in ["det-model", "rec-model", "cls-model", "rec-dict"]:
        run.add_argument("--" + name, type=Path, required=True)
    review = commands.add_parser("review-ocr")
    review.add_argument("--input", type=Path, required=True)
    review.add_argument("--reviewer", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "review-ocr":
            result = approve_candidate(args.input, args.reviewer)
        else:
            engine = create_ocr_engine(args.det_model, args.rec_model, args.cls_model, args.rec_dict)
            result = recognize_file(args.input, args.output_dir, engine)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except IngestionError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:
        print(json.dumps({"error": "OCR 操作失败。", "type": type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

