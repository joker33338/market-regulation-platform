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
from .schemas import TaskList
from pydantic import BaseModel


class TaskStageFile(BaseModel):
    file_id: str
    status: str
    error_code: str | None=None


class TaskStageEvent(BaseModel):
    event_id: str
    timestamp: str
    kind: str
    status: str
    files: list[TaskStageFile]


class TaskLogPage(BaseModel):
    list: list[TaskStageEvent]
    total: int
    page: int
    page_size: int
    source: str
    available: bool
    reason: str | None=None
    historical_backfill: bool=False
    truncated: bool=False
    recording_started_at: str | None=None
from .schemas import (DocumentInfo, DocumentList, HealthResponse, ListResponse, PreviewRequest,
                      PreviewResponse, ReviewDetail, SearchRequest, SearchResponse, StatsResponse, VersionInfo)

def register_tasks(app, service, config, owner, reader):
    router = APIRouter(tags=["tasks"], dependencies=[Depends(owner)])
    pagination = Query(default=1, ge=1)
    size = Query(default=20, ge=1, le=100)

    @router.get('/api/parse/tasks/{task_id}/logs',response_model=TaskLogPage)
    @guarded
    def logs(task_id: str,page: int=pagination,page_size: int=size,
             date_from: datetime | None=None,date_to: datetime | None=None,identity=Depends(owner)):
        from .document_query import validate_window
        validate_window(date_from,date_to)
        task=service.repository.get(task_id,identity)
        events=task.get('stage_events',[])
        rows=[event for event in reversed(events)
              if (date_from is None or datetime.fromisoformat(event['timestamp'])>=date_from)
              and (date_to is None or datetime.fromisoformat(event['timestamp'])<=date_to)]
        return {**page_of(rows,page,page_size,'sqlite.parse_tasks.payload.stage_events'),
                'available':bool(events),'reason':None if events else 'historical_events_not_recorded',
                'historical_backfill':False,'truncated':task.get('stage_events_truncated',False),
                'recording_started_at':task.get('stage_events_started_at')}

    @router.get("/api/parse/tasks", response_model=TaskList)
    @guarded
    def tasks(page: int = pagination, page_size: int = size, status: str | None = Query(None, max_length=40),
              engine: str | None = Query(None, max_length=80), identity=Depends(owner)):
        rows = service.repository.owned_tasks(identity)
        if status:
            rows = [task for task in rows if task["status"] == status]
        if engine:
            rows = [task for task in rows if any(engine in (file.get("selected_engine") or []) for file in task["files"])]
        return page_of([safe({**public(task), "elapsed_seconds": task.get("elapsed_seconds"),
                              "file_mappings": [{"file_id": file["id"], "source_file_id": file.get("source_file_id"),
                                                 "database_parse_id": file.get("database_parse_id")}
                                                for file in task["files"]]}) for task in rows],
                       page, page_size, "sqlite.parse_tasks")


    app.include_router(router)
