"""Preview by default; database initialization and publication are explicit commands."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qa_core.config.settings import ROOT, Settings
from qa_core.governance.kb_versions import publish, rollback
from qa_core.indexing.document_loaders import collect_files, load_file
from qa_core.indexing.service import ingest_documents, preview_documents
from qa_core.indexing.source_adapters import load_pg_documents
from qa_core.retrieval.models import create_embeddings
from qa_core.storage.database import Database
from qa_core.utils import IngestionError


def parser():
    result = argparse.ArgumentParser(description="法律知识库离线入库 MVP")
    commands = result.add_subparsers(dest="command", required=True)
    for name in ["init-db", "ingest", "publish", "rollback", "versions", "query"]:
        command = commands.add_parser(name)
        group = command.add_mutually_exclusive_group()
        group.add_argument("--database", type=Path, help="本地 SQLite 文件；不会自动选择生产连接")
        group.add_argument("--postgres", action="store_true", help="显式使用环境变量 PG_DSN")
        if name in {"ingest", "query"}:
            command.add_argument("--backend", choices=["local", "http", "demo"], default=None)
            command.add_argument("--dimension", type=int, default=None)
        if name in {"publish", "rollback"}:
            command.add_argument("--version", required=True)
        if name == "ingest":
            sources = command.add_mutually_exclusive_group(required=True)
            sources.add_argument("--input", type=Path)
            sources.add_argument("--source-postgres", action="store_true", help="只读 SOURCE_PG_DSN")
            command.add_argument("--law-name")
            command.add_argument("--law-id", help="单文件的稳定法规身份；修订继续使用相同值")
            command.add_argument("--source-main", default="national_laws_regulations")
            command.add_argument("--source-detail", default="national_laws_regulations_detail")
            command.add_argument("--limit-laws", type=int, default=0)
            command.add_argument("--max-chars", type=int, default=800)
            command.add_argument("--batch-size", type=int, default=8)
            command.add_argument("--write", action="store_true", help="构建 STAGED；默认只预览")
            command.add_argument("--version")
            command.add_argument("--full-snapshot", action="store_true",
                                 help="完整权威输入，缺失文档不继承；抽样模式禁止使用")
            command.add_argument("--report", type=Path)
        if name == "query":
            command.add_argument("question")
            command.add_argument("--generate", action="store_true")
    return result


def open_database(args) -> Database:
    if args.postgres:
        if not os.getenv("PG_DSN"):
            raise IngestionError("--postgres 需要显式设置 PG_DSN；没有内置数据库账号。")
        return Database(pg_dsn=os.environ["PG_DSN"])
    if args.database is None:
        raise IngestionError("数据库操作需要 --database 路径或 --postgres。")
    if args.command != "init-db" and not args.database.is_file():
        raise IngestionError("本地数据库不存在，请先执行 init-db。")
    return Database(sqlite_path=args.database)


def input_documents(args):
    if args.source_postgres:
        if not os.getenv("SOURCE_PG_DSN"):
            raise IngestionError("数据库源读取需要显式设置 SOURCE_PG_DSN。")
        if args.limit_laws < 0:
            raise IngestionError("--limit-laws 不能为负数。")
        return load_pg_documents(os.environ["SOURCE_PG_DSN"], main_table=args.source_main,
                                 detail_table=args.source_detail, limit_laws=args.limit_laws)
    files = collect_files(args.input)
    if (args.law_id or args.law_name) and len(files) != 1:
        raise IngestionError("--law-id/--law-name 仅适用于单文件；多文件请分批构建。")
    return (load_file(path, law_name=args.law_name, law_id=args.law_id) for path in files)


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    database = None
    try:
        settings = Settings.from_env()
        if getattr(args, "backend", None):
            settings = replace(settings, embedding_backend=args.backend)
        if getattr(args, "dimension", None) is not None:
            settings = replace(settings, embedding_dimension=args.dimension)
        elif settings.embedding_backend == "demo":
            settings = replace(settings, embedding_dimension=32)
        if args.command == "ingest":
            if args.full_snapshot and args.limit_laws:
                raise IngestionError("抽样 limit 与全量快照不能同时使用。")
            if args.batch_size < 1 or args.batch_size > 128:
                raise IngestionError("--batch-size 必须在 1–128 之间。")
            settings = replace(settings, max_chunk_chars=args.max_chars, batch_size=args.batch_size)
            documents = input_documents(args)
            if not args.write:
                result = preview_documents(documents, max_chars=args.max_chars)
                if args.report:
                    args.report.parent.mkdir(parents=True, exist_ok=True)
                    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                result = {key: value for key, value in result.items() if key != "documents"}
                result["report"] = str(args.report) if args.report else None
            else:
                if not args.version:
                    raise IngestionError("--write 必须指定新的 --version。")
                database = open_database(args)
                result = ingest_documents(documents, database=database, embeddings=create_embeddings(settings),
                                          settings=settings, version=args.version, full_snapshot=args.full_snapshot)
                if args.report:
                    args.report.parent.mkdir(parents=True, exist_ok=True)
                    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            database = open_database(args)
            if args.command == "init-db":
                database.initialize()
                result = {"initialized": True, "storage": "postgresql" if database.postgres else "sqlite"}
            elif args.command == "publish":
                result = publish(database, args.version)
            elif args.command == "rollback":
                result = rollback(database, args.version)
            elif args.command == "versions":
                result = {"active": database.active_version(), "versions": database.list_versions()}
            else:
                from query import ask
                result = ask(args.question, stream=False, database=database,
                             embeddings=create_embeddings(settings), generate=args.generate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except IngestionError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:
        # 驱动和 HTTP 异常可能含凭据，不回显异常正文或 DSN。
        print(json.dumps({"error": "操作失败，未输出可能包含凭据的异常正文。",
                          "type": type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if database is not None:
            database.close()


if __name__ == "__main__":
    raise SystemExit(main())

