"""离线入库前质检：本地解析结果→法规/案例切分→完整性报告，不写知识库。"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qa_core.document_parsing.document_router import DocumentParser
from qa_core.document_parsing.schemas import DocumentResult
from qa_core.indexing.preview import preview_chunks
from qa_core.utils import IngestionError, file_sha256


def load_result(args):
    if args.input:
        before = file_sha256(args.input)
        with DocumentParser() as parser:
            result = parser.parse(args.input)
        if before != file_sha256(args.input) or before != result.document_id:
            raise IngestionError("源文件摘要发生变化，停止质检。")
        return result
    if args.result:
        return DocumentResult.from_dict(json.loads(args.result.read_text(encoding="utf-8-sig")))
    import psycopg2
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    connection = psycopg2.connect(config["PARSING_RESULT_PG_DSN"], connect_timeout=5)
    try:
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT original_result FROM document_review.documents WHERE parse_id=%s", (args.parse_id,))
            row = cursor.fetchone()
        if not row:
            raise IngestionError("没有找到指定解析记录。")
        return DocumentResult.from_dict(json.loads(row[0]) if isinstance(row[0], str) else row[0])
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="本地原文件，使用既有离线解析器")
    source.add_argument("--result", type=Path, help="已有normalized.json，避免重复OCR")
    source.add_argument("--parse-id", help="从用户指定数据库只读获取已有解析结果")
    parser.add_argument("--config", type=Path, default=ROOT/"local/parsing-runtime.json")
    parser.add_argument("--document-type", choices=("law", "case"), required=True)
    parser.add_argument("--max-chars", type=int, default=800)
    parser.add_argument("--output", type=Path, required=True, help="输出私密正文与质检JSON到忽略目录")
    args = parser.parse_args(argv)
    if not 64 <= args.max_chars <= 1600:
        parser.error("片段上限应在64至1600字之间；未加载文件或解析器。")
    output = args.output.resolve()
    if not (output.is_relative_to(ROOT/"local") or output.is_relative_to(Path("/state"))):
        parser.error("含原文的质检输出只能位于项目local目录或容器/state目录。")
    target = output / "chunk-preview.json"
    inputs = [path for path in (args.input, args.result, args.config if args.parse_id else None) if path is not None]
    if any(target.resolve() == path.resolve() for path in inputs):
        parser.error("输出与输入或配置文件相同，拒绝覆盖。")
    try:
        report = preview_chunks(load_result(args), args.document_type, max_chars=args.max_chars)
        output.mkdir(parents=True, exist_ok=True)
        # 同目录原子替换，避免半写文件，也不跟随已有输出文件的符号链接。
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output,
                                             prefix=".chunk-preview-", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        summary = {key: report[key] for key in ("mode", "document_type", "chunk_count", "parent_count", "quality",
                                               "requires_review", "rag_index_written")}
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except Exception as exc:
        # 解析/连接错误可能含真实路径或凭据，只输出安全类型。
        print(json.dumps(dict(status="FAILED", error_type=type(exc).__name__), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
