"""仅报告当前API进程实测资源，不暴露主机路径或冒充宿主机监控。"""
from datetime import datetime, timezone
import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel


class ProcessResources(BaseModel):
    available: bool
    reason: str | None = None
    scope: str = "api_process"
    sampled_at: str
    memory_rss_bytes: int | None = None
    cpu_user_seconds: float | None = None
    cpu_system_seconds: float | None = None
    uptime_seconds: float | None = None
    threads: int | None = None


def register_resources(app, owner):
    router = APIRouter(tags=['monitoring'], dependencies=[Depends(owner)])

    @router.get('/api/system/resources', response_model=ProcessResources)
    def resources():
        sampled_at = datetime.now(timezone.utc).isoformat()
        try:
            import psutil
            process = psutil.Process()
            with process.oneshot():
                cpu = process.cpu_times()
                return ProcessResources(available=True, sampled_at=sampled_at,
                    memory_rss_bytes=process.memory_info().rss, cpu_user_seconds=cpu.user,
                    cpu_system_seconds=cpu.system, uptime_seconds=max(0, time.time()-process.create_time()),
                    threads=process.num_threads())
        except Exception:
            # 不返回内部异常或用零值掩盖探测失败。
            return ProcessResources(available=False, reason='process_metrics_unavailable', sampled_at=sampled_at)

    app.include_router(router)
