"""前端查询适配：复用任务身份、解析结果及 public 知识库，禁止隐式业务写入。"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.document_parsing.mineru_api import public
from qa_core.utils import IngestionError
from .schemas import (DocumentInfo, DocumentList, HealthResponse, ListResponse, PreviewRequest,
                      PreviewResponse, ReviewDetail, SearchRequest, SearchResponse, StatsResponse,
                      VersionInfo)


def safe(value):
    """保留解析正文；去除运行目录、认证数据及可能含内部路径的异常详情。"""
    if isinstance(value, dict):
        return {key: safe(item) for key, item in value.items()
                if key.lower() not in {"path", "dsn", "token", "api_key", "password", "authorization",
                                       "raw_result_location", "error_message", "traceback", "authorization_context"}
                and not key.lower().endswith(("_path", "_dir", "_root", "_token", "_secret"))}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    return value


def guarded(function):
    """查询失败显式返回不可用，不把连接异常及驱动调试文本发给浏览器。"""
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except MinerUError:
            raise
        except Exception:
            raise MinerUError("read_service_unavailable", 503) from None
    return wrapped


def page_of(rows, page, page_size, source):
    return {"list": rows[(page - 1) * page_size:page * page_size], "total": len(rows),
            "page": page, "page_size": page_size, "source": source}


from .read_store import ReviewReader

class FrontendReader:
    def __init__(self, service, config, *, review=None, kb_factory=None, embeddings_factory=None):
        self.service, self.config = service, config
        dsn = getattr(service.result_sink, "dsn", None)
        self.review = review or (ReviewReader(dsn) if dsn else None)

    def root(self, owner):
        # GET 不创建目录；上传接口才拥有生成文件的职责。
        return self.config.result_dir / "sources" / hashlib.sha256(owner.encode()).hexdigest()

    def upload(self, owner, file_id):
        if not re.fullmatch(r"[0-9a-f]{32}", file_id):
            raise MinerUError("source_not_found", 404)
        root = self.root(owner)
        path = root / (file_id + ".json")
        if not path.is_file():
            raise MinerUError("source_not_found", 404)
        value = json.loads(path.read_text(encoding="utf-8"))
        suffix = Path(value["file_name"]).suffix.lower()
        from qa_core.document_parsing.mineru_service import SUFFIXES
        if suffix not in SUFFIXES:
            raise MinerUError("unsupported_file", 415)
        expected = root / (file_id + suffix)
        # 只允许 owner 目录内按上传 ID 生成的文件，不能接受任意绝对路径或链接逃逸。
        if (expected.resolve().parent != root.resolve() or expected.is_symlink() or path.is_symlink()
                or Path(value["path"]).resolve() != expected.resolve()):
            raise MinerUError("source_not_found", 404)
        value["file_id"] = file_id
        value["uploaded_at"] = value.get("uploaded_at") or datetime.fromtimestamp(
            path.stat().st_mtime, timezone.utc).isoformat()
        value["uploaded_at_source"] = "upload_metadata" if "uploaded_at" in json.loads(
            path.read_text(encoding="utf-8")) else "metadata_mtime"
        return value, expected

    def history(self, owner, file_id, tasks=None):
        tasks = self.service.repository.owned_tasks(owner) if tasks is None else tasks
        return [(task, file) for task in tasks for file in task["files"]
                if file.get("source_file_id") == file_id]

    def documents(self, owner):
        tasks = self.service.repository.owned_tasks(owner)
        by_source = {}
        for task in tasks:
            for file in task["files"]:
                by_source.setdefault(file.get("source_file_id"), []).append((task, file))
        rows = []
        for path in self.root(owner).glob("*.json"):
            value, _ = self.upload(owner, path.stem)
            history = by_source.get(path.stem, [])
            task, file = history[0] if history else (None, None)
            status = file["status"] if file else "uploaded"
            if file and status == "completed" and file.get("requires_review"):
                status = "pending_review"
            suffix = Path(value["file_name"]).suffix.lower()[1:]
            rows.append({"file_id": path.stem, "file_name": value["file_name"],
                         "doc_type": suffix if suffix in {"pdf", "docx"} else "image",
                         "size_bytes": value["bytes"], "sha256": value["sha256"],
                         "uploaded_at": value["uploaded_at"], "uploaded_at_source": value["uploaded_at_source"],
                         "status": status, "latest_task_id": task["id"] if task else None,
                         "parse_count": len(history)})
        return sorted(rows, key=lambda row: (row["uploaded_at"], row["file_id"]), reverse=True)

    def review_store(self):
        if self.review is None:
            raise MinerUError("review_database_not_configured", 503)
        return self.review

    def task_file(self, owner, task_id, file_id):
        task = self.service.repository.get(task_id, owner)
        for file in task["files"]:
            if file["id"] == file_id:
                return task, file
        raise MinerUError("file_not_found", 404)

    def candidate(self, task, file, *, local=False):
        if local:
            if not task.get("routing_protocol"):
                return None
            path = self.config.result_dir / task["id"] / file["id"] / "local-candidate.json"
        else:
            directory = file.get("result_path") or (file.get("local_result_path") if task.get("routing_protocol") else None)
            if not directory:
                return None
            path = Path(directory) / "normalized.json"
        root = self.config.result_dir.resolve()
        if not path.resolve().is_relative_to(root) or not path.is_file():
            return None
        if path.stat().st_size > self.config.max_expanded_bytes:
            raise MinerUError("result_too_large", 503)
        return json.loads(path.read_text(encoding="utf-8"))

    def review_detail(self, owner, parse_id):
        row = self.review_store().detail(owner, parse_id)
        location = row["source_location"]
        task_id, source_id = location.get("local_task_id"), location.get("source_file_id")
        candidate = None
        if task_id and source_id:
            try:
                task = self.service.repository.get(task_id, owner)
            except MinerUError as exc:
                if exc.status != 404:
                    raise
            else:
                for file in task["files"]:
                    # 使用已持久映射交叉核验；绝不从 parse_id 推导文件 ID。
                    if file.get("database_parse_id") == parse_id and file.get("source_file_id") == source_id:
                        candidate = self.candidate(task, file, local=True)
        return safe({**row, "task_id": task_id, "source_file_id": source_id,
                     "local_candidate": candidate, "local_candidate_available": candidate is not None,
                     "review_write_supported": False})
