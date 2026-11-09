"""Opt-in authenticated API factory. Run one ASGI process with the pilot SQLite store."""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from .mineru_config import MinerUConfig
from .mineru_client import MinerUClient, MinerUError, validate_name
from .mineru_repository import TaskRepository
from .mineru_service import MinerUService


def public(task):
    return {"task_id": task["id"], "status": task["status"], "mode": task["mode"],
            "cancel_requested": task.get("cancel_requested", False),
            "cancel_scope": task.get("cancel_scope"), "provider": task.get("provider", "self_hosted"),
            "created_at": task["created_at"], "completed_at": task["completed_at"], "error": task["error"],
            "files": [{"file_id": file["id"], "file_name": file["file_name"], "sha256": file["sha256"],
                       "database_parse_id": file.get("database_parse_id"),
                       "selected_engine": file.get('selected_engine'), "requires_review": file.get('requires_review'),
                       "fallback_reason": file.get('fallback_reason'),
                       "status": file["status"], "error": file.get("error") or
                       ({"code": file.get("remote", {}).get("error", {}).get("code")} if file.get("remote", {}).get("error") else None)}
                      for file in task["files"]]}


def redact_paths(value):
    if isinstance(value, dict):
        return {key: redact_paths(item) for key, item in value.items()
                if key not in {"file_path", "source_path", "raw_result_location", "result_path"}}
    if isinstance(value, list):
        return [redact_paths(item) for item in value]
    return value


def create_app(config=None, *, tokens=None, service=None, dual_config=None, cloud_grants=None, batch_authorizer=None):
    # Optional API dependencies do not affect import of CLI/business modules.
    from fastapi import Depends, FastAPI, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    config = config or MinerUConfig.from_env()
    from .dual_engine import DualEngineConfig, DualEngineRouter
    dual_config = dual_config or DualEngineConfig.from_env()
    tokens = tokens if tokens is not None else json.loads(os.getenv("PARSING_API_TOKENS_JSON", "{}"))
    if not tokens or any(len(token) < 32 or not owner for token, owner in tokens.items()):
        raise MinerUError("api_auth_configuration_required", 503)
    if service is None:
        dual_router = None
        if dual_config.enabled:
            remote_config = replace(config, mode='remote', provider='official', api_url='https://mineru.net/api', output_formats=('default',))
            config = replace(config, mode='local', provider='self_hosted', api_url='')
            if cloud_grants is None:
                grant_file = os.getenv('DUAL_OCR_GRANTS_FILE')
                cloud_grants = json.loads(Path(grant_file).read_text(encoding='utf-8')) if grant_file else {}
            if dual_config.authorization_mode == 'TEST_BATCH' and batch_authorizer is None:
                from .test_batch_authorization import TrustedTestBatch
                manifest = os.getenv('DUAL_OCR_TEST_BATCH_MANIFEST')
                if not manifest:
                    raise MinerUError('test_batch_configuration_required', 503)
                try:
                    batch_authorizer = TrustedTestBatch(manifest, owner=os.getenv('DUAL_OCR_TEST_BATCH_OWNER'),
                                                        batch_id=os.getenv('DUAL_OCR_TEST_BATCH_ID'))
                except ValueError as exc:
                    raise MinerUError('test_batch_configuration_required', 503) from exc
            dual_router = DualEngineRouter(dual_config, remote_config, grants=cloud_grants,
                                           batch_authorizer=batch_authorizer)
        from .mineru_mock import mock_transport
        repository = TaskRepository(config.result_dir / "tasks.sqlite3")
        if config.provider == "official":
            from .mineru_official import OfficialMinerUClient
            if config.mode != "remote":
                raise MinerUError("official_provider_requires_remote_mode", 400)
            client = OfficialMinerUClient(config)
        else:
            client = None if config.mode == "local" else MinerUClient(config, transport=mock_transport() if config.mode == "mock" else None)
        sink = None
        if os.getenv("PARSING_RESULT_PG_DSN"):
            from qa_core.storage.parsing_results import PostgresResultSink
            sink = PostgresResultSink(os.environ["PARSING_RESULT_PG_DSN"])
        service = MinerUService(config, repository, client, result_sink=sink, dual_router=dual_router)
    workers = []

    async def worker(index):
        while True:
            tasks = await asyncio.to_thread(service.repository.resumable, config.queue_size)
            for task in tasks[index::config.concurrency]:
                await service.run(task["id"])
            await asyncio.sleep(0.2)

    @asynccontextmanager
    async def lifespan(app):
        if config.enabled:
            workers.extend(asyncio.create_task(worker(i)) for i in range(config.concurrency))
        yield
        for job in workers:
            job.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        if service.client:
            await service.client.close()

    app = FastAPI(title="Document parsing", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service

    @app.get("/", include_in_schema=False)
    async def upload_page():
        from fastapi.responses import FileResponse
        return FileResponse(Path(__file__).with_name("parsing_upload.html"), media_type="text/html")

    @app.exception_handler(MinerUError)
    async def parse_error(request, exc):
        status = exc.status if exc.status in {400, 401, 404, 409, 413, 415, 429, 503} else 502
        return JSONResponse({"error": {"code": exc.code}}, status_code=status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({"error": {"code": "invalid_request"}}, status_code=422)

    async def owner(request: Request):
        authorization = request.headers.get("authorization", "")
        token = authorization[7:] if authorization.startswith("Bearer ") else ""
        for expected, identity in tokens.items():
            if hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
                return identity
        raise MinerUError("unauthorized", 401)

    @app.get("/api/parse/info")
    async def info(identity=Depends(owner)):
        return {"mode": config.mode, "provider": config.provider, "enabled": config.enabled,
                "database_enabled": service.result_sink is not None, 'dual_engine_enabled': bool(service.dual_router)}

    def upload_root(identity):
        root = config.result_dir / "sources" / hashlib.sha256(identity.encode()).hexdigest()
        root.mkdir(parents=True, exist_ok=True)
        return root

    @app.post("/api/parse/files", status_code=201)
    async def upload(request: Request, file_name: str, identity=Depends(owner)):
        if not config.enabled:
            raise MinerUError("parser_disabled", 503)
        validate_name(file_name)
        from .mineru_service import SUFFIXES
        if Path(file_name).suffix.lower() not in SUFFIXES:
            raise MinerUError("unsupported_file", 415)
        fid = uuid4().hex
        root = upload_root(identity)
        target = root / (fid + Path(file_name).suffix.lower())
        size, digest = 0, hashlib.sha256()
        try:
            with target.open("xb") as stream:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > config.max_file_bytes:
                        raise MinerUError("file_too_large", 413)
                    await asyncio.to_thread(stream.write, chunk)
                    digest.update(chunk)
            if not size:
                raise MinerUError("empty_upload", 400)
            # Check headers against suffix without loading models or writing to a database.
            def read_header():
                with target.open("rb") as stream:
                    return stream.read(8)
            signature = await asyncio.to_thread(read_header)
            suffix = target.suffix
            valid = signature.startswith(b"%PDF-") if suffix == ".pdf" else signature.startswith(b"PK") if suffix == ".docx" else signature.startswith(b"\x89PNG\r\n\x1a\n") if suffix == ".png" else signature.startswith(b"\xff\xd8\xff")
            if not valid:
                raise MinerUError("file_type_mismatch", 415)
            metadata = {"file_name": file_name, "path": str(target.resolve()), "sha256": digest.hexdigest(), "bytes": size}
            await asyncio.to_thread((root / (fid + ".json")).write_text, json.dumps(metadata), encoding="utf-8")
        except BaseException:
            target.unlink(missing_ok=True)  # only the generated incomplete upload, never a corpus path
            raise
        return {"file_id": fid, "sha256": digest.hexdigest(), "bytes": size}

    @app.post("/api/parse/tasks", status_code=202)
    async def submit(request: Request, identity=Depends(owner)):
        if int(request.headers.get("content-length", "0")) > 16384:
            raise MinerUError("request_too_large", 413)
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 16384:
                raise MinerUError("request_too_large", 413)
        try:
            body = json.loads(data)
            ids = body["file_ids"]
            if set(body) - {"file_ids", "strategy", "allow_cloud_fallback", "sensitive"} or not isinstance(ids, list) or not 1 <= len(ids) <= config.max_files:
                raise ValueError()
            paths = []
            for fid in ids:
                if not isinstance(fid, str) or len(fid) != 32 or any(c not in "0123456789abcdef" for c in fid):
                    raise ValueError()
                metadata = json.loads((upload_root(identity) / (fid + ".json")).read_text(encoding="utf-8"))
                paths.append((metadata["file_name"], Path(metadata["path"]), fid))
        except (ValueError, KeyError, TypeError, OSError):
            raise MinerUError("invalid_file_ids", 400) from None
        key = request.headers.get("idempotency-key", "")
        options = {key: value for key, value in body.items() if key != 'file_ids'}
        task, _ = await service.submit(identity, key, paths, **({'parse_options': options} if options else {}))
        return public(task)

    @app.get("/api/parse/tasks/{task_id}")
    async def detail(task_id: str, identity=Depends(owner)):
        return public(await asyncio.to_thread(service.repository.get, task_id, identity))

    @app.get("/api/parse/tasks/{task_id}/errors")
    async def errors(task_id: str, identity=Depends(owner)):
        return public(await asyncio.to_thread(service.repository.get, task_id, identity))

    @app.post("/api/parse/tasks/{task_id}/resume", status_code=202)
    async def resume(task_id: str, identity=Depends(owner)):
        return public(await service.resume(task_id, identity))

    @app.post("/api/parse/tasks/{task_id}/cancel")
    async def cancel(task_id: str, identity=Depends(owner)):
        return public(await service.cancel(task_id, identity))

    @app.get("/api/parse/tasks/{task_id}/results")
    async def results(task_id: str, identity=Depends(owner)):
        task = await asyncio.to_thread(service.repository.get, task_id, identity)
        values = []
        for file in task["files"]:
            result_path = file["result_path"] or (file.get('local_result_path') if task.get('routing_protocol') else None)
            if result_path:
                path = Path(result_path) / "normalized.json"
                if path.is_file():
                    value = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
                    values.append({"file_id": file["id"], "document": redact_paths(value)})
        return {"task_id": task_id, "status": task["status"], "results": values}

    @app.get("/api/parse/tasks/{task_id}/files/{file_id}/artifact")
    async def artifact(task_id: str, file_id: str, identity=Depends(owner)):
        from fastapi.responses import FileResponse
        task = await asyncio.to_thread(service.repository.get, task_id, identity)
        for file in task["files"]:
            if file["id"] == file_id and file["status"] == "completed" and file["result_path"]:
                path = Path(file["result_path"]) / "artifact.bin"
                if path.is_file():
                    return FileResponse(path, media_type="application/octet-stream", filename=file_id + ".bin")
        raise MinerUError("artifact_not_found", 404)
    return app
