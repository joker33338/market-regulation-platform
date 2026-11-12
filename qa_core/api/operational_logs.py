"""结构化运行日志；只记录白名单状态，不记录请求正文、凭证或原始路径。"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from filelock import FileLock
from pydantic import BaseModel

from .common import guarded, page_of
from .document_query import validate_window


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class OperationalLog(BaseModel):
    event_id: str
    timestamp: str
    principal_id: str | None
    actor_confirmed: bool=True
    method: str
    route: str
    status_code: int
    duration_ms: float
    level: str


class OperationalLogPage(BaseModel):
    list: list[OperationalLog]
    total: int
    page: int
    page_size: int
    source: str = 'private_operational_journal'
    scope: str = 'current_principal'
    historical_backfill: bool = False
    truncated: bool = False


class OperationalJournal:
    def __init__(self, root):
        self.root=Path(root)/'.api-request-logs'

    def location(self, principal_id):
        return self.root/(hashlib.sha256(principal_id.encode()).hexdigest()+'.jsonl')

    def append(self, principal_id, item):
        self.root.mkdir(parents=True,exist_ok=True)
        path=self.location(principal_id)
        with FileLock(str(path)+'.lock',timeout=2):
            with path.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(item,ensure_ascii=False)+'\n')

    def rows(self, principal_id):
        if principal_id is None:
            rows=[];truncated=False
            for path in self.root.glob('*.jsonl'):
                with FileLock(str(path)+'.lock',timeout=2),path.open(encoding='utf-8') as stream:
                    rows.extend(json.loads(line) for line in stream)
            return sorted(rows,key=lambda row:row['timestamp'],reverse=True)[:10000],len(rows)>10000
        path=self.location(principal_id)
        if not path.exists():
            return [],False
        from collections import deque
        with FileLock(str(path)+'.lock',timeout=2),path.open(encoding='utf-8') as stream:
            recent=deque(maxlen=10000)
            total=0
            for line in stream:
                total+=1
                recent.append(json.loads(line))
        return list(reversed(recent)),total>10000


def register_operational_logs(app, config, principal):
    journal=OperationalJournal(config.result_dir)
    app.state.operational_journal=journal
    from .document_delete import DocumentDeletionError
    router=APIRouter(tags=['monitoring'],dependencies=[Depends(principal)],
                     responses={code:{'model':DocumentDeletionError} for code in (401,403,422,503)})

    @app.middleware('http')
    async def record(request, call_next):
        started=time.perf_counter()
        response=await call_next(request)
        identity=getattr(request.state,'principal',None)
        if request.url.path.startswith('/api/'):
            route=getattr(request.scope.get('route'),'path',None) or 'unmatched_api'
            # 只允许路由模板；未匹配请求不能把任意用户路径写进日志。
            if route:
                item={'event_id':uuid4().hex,'timestamp':utc_now(),'principal_id':identity.principal_id if identity else None,
                      'actor_confirmed':identity is not None,
                      'method':request.method if request.method in {'GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'} else 'OTHER',
                      'route':route,'status_code':response.status_code,
                      'duration_ms':round((time.perf_counter()-started)*1000,3),
                      'level':'error' if response.status_code>=500 else 'warning' if response.status_code>=400 else 'info'}
                try:
                    import asyncio
                    await asyncio.to_thread(journal.append,identity.principal_id if identity else '_unconfirmed_',item)
                except Exception:
                    # 业务回执不能被日志故障改写；读取时明确暴露不可用状态。
                    app.state.operational_log_failed=True
        return response

    def endpoint(errors_only):
        @guarded
        def listing(page: int=Query(1,ge=1),page_size: int=Query(20,ge=1,le=100),
                    date_from: datetime | None=None,date_to: datetime | None=None,
                    level: str | None=Query(None,pattern='^(info|warning|error)$'),identity=Depends(principal)):
            from qa_core.document_parsing.mineru_client import MinerUError
            validate_window(date_from,date_to)
            if getattr(app.state,'operational_log_failed',False):
                raise MinerUError('operational_log_unavailable',503)
            rows,truncated=journal.rows(None if identity.is_admin else identity.principal_id)
            rows=[row for row in rows if (not errors_only or row['status_code']>=400)
                  and (level is None or row['level']==level)
                  and (date_from is None or datetime.fromisoformat(row['timestamp'])>=date_from)
                  and (date_to is None or datetime.fromisoformat(row['timestamp'])<=date_to)]
            return {**page_of(rows,page,page_size,'private_operational_journal'),'truncated':truncated,
                    'scope':'all_principals' if identity.is_admin else 'current_principal'}
        return listing

    router.add_api_route('/api/system/api-logs',endpoint(False),methods=['GET'],response_model=OperationalLogPage,
                         description='当前principal的真实API请求元数据；不含凭证、正文、查询串或对象路径；最多查询最近10000条。')
    router.add_api_route('/api/system/error-logs',endpoint(True),methods=['GET'],response_model=OperationalLogPage,
                         description='当前principal的HTTP 4xx/5xx请求日志，不是OCR异常堆栈；无历史回填。')
    app.include_router(router)
