"""独立前端静态服务与同源代理；不加载业务服务、模型或数据库。"""
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from starlette.staticfiles import StaticFiles
from starlette.background import BackgroundTask


ROOT = Path(__file__).resolve().parent / "dist"
BACKEND = "http://market-regulation-app-1:8180"
HOP_HEADERS = {b"connection", b"keep-alive", b"proxy-authenticate", b"proxy-authorization",
               b"te", b"trailer", b"transfer-encoding", b"upgrade", b"host"}


def forwarded_headers(headers):
    """保留认证、Range 和重复响应头，移除逐跳传输头。"""
    blocked = set(HOP_HEADERS)
    for key, value in headers:
        if key.lower() == b"connection":
            blocked.update(item.strip().lower() for item in value.split(b","))
    return [(key, value) for key, value in headers if key.lower() not in blocked]


@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=5), trust_env=False,
                                 follow_redirects=False) as client:
        app.state.client = client
        yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.get("/healthz")
async def health():
    return PlainTextResponse("ok\n")


@app.api_route("/api/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy(request: Request, path: str):
    # 固定目标，绝不接受客户端传入的上游地址；不重试有副作用的请求。
    target = httpx.URL(BACKEND).copy_with(raw_path=request.scope["raw_path"] +
                                        (b"?" + request.scope["query_string"] if request.scope["query_string"] else b""))
    upstream_request = app.state.client.build_request(
        request.method, target, headers=forwarded_headers(request.headers.raw), content=request.stream())
    try:
        upstream = await app.state.client.send(upstream_request, stream=True)
    except httpx.RequestError:
        return JSONResponse({"error": {"code": "backend_unavailable"}}, status_code=502)
    response = StreamingResponse(upstream.aiter_raw(), status_code=upstream.status_code,
                                 background=BackgroundTask(upstream.aclose))
    response.raw_headers = forwarded_headers(upstream.headers.raw)
    return response


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            # 静态资源缺失必须返回 404；页面路由交由 Vue 处理。
            if path.startswith("assets/") or Path(path).suffix:
                raise
            response = FileResponse(ROOT / "index.html")
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
        return response


app.mount("/", FrontendFiles(directory=ROOT, html=True), name="frontend")
