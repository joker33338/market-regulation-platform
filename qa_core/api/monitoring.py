"""现有业务服务的权限隔离 HTTP 查询适配。"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.document_parsing.mineru_api import public
from qa_core.utils import IngestionError
from .common import guarded, page_of, safe
from .schemas import (DocumentInfo, DocumentList, HealthResponse, ListResponse, PreviewRequest,
                      PreviewResponse, ReviewDetail, SearchRequest, SearchResponse, StatsResponse, VersionInfo)

def register_monitoring(app, service, config, owner, reader):
    router = APIRouter(tags=["monitoring"], dependencies=[Depends(owner)])
    pagination = Query(default=1, ge=1)
    size = Query(default=20, ge=1, le=100)

    @router.get("/api/stats/overview", response_model=StatsResponse)
    @guarded
    def stats(days: int = Query(14, ge=1, le=366), identity=Depends(owner)):
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=days)
        tasks = service.repository.owned_tasks(identity)
        selected = [task for task in tasks if datetime.fromisoformat(task["created_at"]) >= since]
        # 引擎按文件计数；一个任务可能有多个文件和引擎，不能伪称任务数。
        engines = Counter(engine for task in selected for file in task["files"]
                          for engine in (file.get("selected_engine") or ["unrecorded"]))
        trends = Counter(task["created_at"][:10] for task in selected)
        try:
            pg = {"available": True, **reader.review_store().stats(identity)}
        except Exception:
            pg = {"available": False, "total": None, "requires_review": None}
        uploads = reader.documents(identity)
        return {"generated_at": now.isoformat(), "window": {"since": since.isoformat(), "until": now.isoformat()},
                "uploads": {"source": "owner_upload_metadata", "scope": "all_time", "total": len(uploads)},
                "tasks": {"source": "sqlite.parse_tasks", "scope": "window", "total": len(selected),
                          "status_distribution": dict(Counter(task["status"] for task in selected)),
                          "engine_file_selections": dict(engines), "created_daily": dict(sorted(trends.items()))},
                "parsed_documents": {"source": "document_review.documents", "scope": "all_time", **pg},
                "recent_tasks": [safe(public(task)) for task in selected[:10]]}

    @router.get("/api/system/health", response_model=HealthResponse)
    def health():
        components = {"fastapi": {"state": "ONLINE", "check": "request_handled"}}
        try:
            with service.repository.connect() as connection:
                connection.execute("SELECT 1 FROM parse_tasks LIMIT 0")
            components["task_store"] = {"state": "ONLINE", "check": "read_only_query"}
        except Exception:
            components["task_store"] = {"state": "ERROR", "check": "read_only_query"}
        try:
            reader.review_store().health()
            components["postgresql"] = {"state": "ONLINE", "check": "read_only_query"}
        except Exception:
            components["postgresql"] = {"state": "UNKNOWN" if reader.review else "NOT_CONFIGURED", "check": "read_only_query"}
        from qa_core.document_parsing.config import ParsingConfig
        for name, method in (("paddle_ocr", "ocr"), ("pp_structure", "structure")):
            try:
                ParsingConfig.from_env().validate_models(method)
                ready = True
            except Exception:
                ready = False
            components[name] = {"state": "UNKNOWN", "model_ready": ready, "check": "files_only_no_inference"}
        from qa_core.config.settings import Settings
        try:
            model = Settings.from_env().embedding_model_path
            model_ready = model.is_dir() and (model.parent / "model_manifest.json").is_file()
        except Exception:
            model_ready = False
        components["bge_m3"] = {"state": "UNKNOWN", "model_ready": model_ready, "check": "files_only_no_inference"}
        remote = getattr(getattr(service, "dual_router", None), "remote_config", config)
        components["mineru"] = {"state": "UNKNOWN" if remote.api_key else "NOT_CONFIGURED",
                                "configured": bool(remote.api_key), "check": "configuration_only_no_request"}
        return {"status": "ok" if all(components[key]["state"] == "ONLINE" for key in
                                     ("fastapi", "task_store", "postgresql")) else "degraded", "components": components}


    app.include_router(router)
