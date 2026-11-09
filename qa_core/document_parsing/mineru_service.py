"""Bounded, resumable task lifecycle and source/result associations."""
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from uuid import uuid4

from qa_core.utils import file_sha256, stable_hash
from .mineru_client import MinerUClient, MinerUError, validate_name
from .mineru_artifacts import store_artifacts, normalize_artifacts
from .mineru_repository import TaskRepository

logger = logging.getLogger(__name__)
TERMINAL = {"completed", "partial", "failed", "canceled"}
REMOTE = TERMINAL | {"waiting-file", "pending", "running"}
SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".docx"}


def now():
    return datetime.now(timezone.utc).isoformat()


class MinerUService:
    def __init__(self, config, repository: TaskRepository, client: MinerUClient | None = None, *, result_sink=None, dual_router=None):
        self.config, self.repository, self.client = config, repository, client
        self.result_sink = result_sink
        self.dual_router = dual_router
        if dual_router and (config.mode != 'local' or not dual_router.config.enabled):
            raise MinerUError('dual_engine_requires_local_task_mode', 400)
        self.root = config.result_dir.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks = {}  # removed after execution; bounded by active workers

    async def submit(self, owner, request_key, inputs, *, parse_options=None):
        if not self.config.enabled:
            raise MinerUError("parser_disabled", 503)
        if not owner or not 1 <= len(request_key) <= 128 or not 1 <= len(inputs) <= self.config.max_files:
            raise MinerUError("invalid_submission", 400)
        if parse_options is not None:
            if not self.dual_router:
                raise MinerUError("dual_engine_unconfigured", 400)
            if (not isinstance(parse_options, dict) or set(parse_options) - {'strategy', 'allow_cloud_fallback', 'sensitive'}
                    or not isinstance(parse_options.get('strategy', 'auto'), str)
                    or parse_options.get('strategy', 'auto') not in {'auto', 'local', 'remote'}
                    or any(type(parse_options.get(key, False)) is not bool for key in ('allow_cloud_fallback', 'sensitive'))):
                raise MinerUError("invalid_parse_options", 400)
        files = []
        for item in inputs:
            name, path = item[:2]
            validate_name(name)
            path = Path(path)
            if Path(name).suffix.lower() not in SUFFIXES or not path.is_file():
                raise MinerUError("unsupported_file", 415)
            size = path.stat().st_size
            if not 0 < size <= self.config.max_file_bytes:
                raise MinerUError("invalid_file_size", 413)
            digest = await asyncio.to_thread(file_sha256, path)
            local_id = uuid4().hex
            files.append({"id": local_id, "source_file_id": item[2] if len(item) == 3 else local_id,
                          "file_name": name, "sha256": digest, "bytes": size,
                          "source_path": str(path.resolve()), "remote_id": None, "status": "created",
                          "uploaded": False, "result_path": None})
        task = {"id": uuid4().hex, "owner": owner, "request_key": request_key,
                "fingerprint": stable_hash([(f["file_name"], f["sha256"]) for f in files], self.config.mode,
                                           self.config.provider, self.config.cloud_model, self.config.api_url,
                                           self.config.tier, self.config.output_formats),
                "status": "created", "remote_id": None, "submission_started": False,
                "created_at": now(), "completed_at": None, "files": files, "error": None,
                "mode": self.config.mode, "api_identity": stable_hash(self.config.api_url),
                "provider": self.config.provider,
                "output_formats": list(self.config.output_formats)}
        if self.dual_router:
            task['parse_options'] = {'strategy': 'auto', 'allow_cloud_fallback': False, 'sensitive': False, **(parse_options or {})}
            task['fingerprint'] = stable_hash(task['fingerprint'], task['parse_options'])
            task['result_root'] = str(self.root)
            task['routing_protocol'] = 'dual-engine-v1'
            if getattr(self.dual_router.config, 'authorization_mode', 'FILE_SHA') == 'TEST_BATCH':
                from .test_batch_authorization import TrustedTestBatch
                authority = self.dual_router.batch_authorizer
                if not isinstance(authority, TrustedTestBatch):
                    raise MinerUError('test_batch_unconfigured', 503)
                try:
                    authority.bind_task(task)
                except ValueError as exc:
                    raise MinerUError('test_batch_binding_mismatch', 403) from exc
                task['fingerprint'] = stable_hash(task['fingerprint'], task['authorization_context'])
        return await asyncio.to_thread(self.repository.create, task, self.config.queue_size)

    def _snapshot(self, task, snapshot):
        if snapshot.get("task_id") != task["remote_id"] or snapshot.get("status") not in REMOTE:
            raise MinerUError("invalid_task_snapshot")
        remote_files = snapshot.get("files", [])
        if (len(remote_files) != len(task["files"]) or len({f.get("file_id") for f in remote_files}) != len(remote_files)
                or {f.get("file_id") for f in remote_files} != {f["remote_id"] for f in task["files"]}):
            raise MinerUError("file_association_mismatch")
        by_id = {file["file_id"]: file for file in remote_files}
        for local in task["files"]:
            remote = by_id[local["remote_id"]]
            if remote.get("status") not in REMOTE - {"partial"}:
                raise MinerUError("invalid_file_status")
            local["remote"] = remote
            local["status"] = remote["status"]
            local["parse"] = remote.get("parse", {})
        task["remote_status"] = snapshot["status"]
        # Remote completion is not local completion until artifacts are durable.
        task["status"] = ("running" if snapshot["status"] in TERMINAL else
                          "uploading" if snapshot["status"] == "waiting-file" else snapshot["status"])

    async def _save(self, task):
        await asyncio.to_thread(self.repository.save, task)
        if self.dual_router:
            current = await asyncio.to_thread(self.repository.get, task['id'])
            task['cancel_requested'] = current.get('cancel_requested', False)

    async def _upload(self, task, file):
        import httpx
        if file["uploaded"]:
            return
        path = Path(file["source_path"])
        if await asyncio.to_thread(file_sha256, path) != file["sha256"]:
            raise MinerUError("source_integrity_mismatch", 409)
        for attempt in range(self.config.max_upload_retries + 1):
            try:
                if await self.client.upload(file["remote"], path):
                    file["uploaded"] = True
                    await self._save(task)
                return
            except (httpx.TransportError, MinerUError):
                # Always query after interrupted PUT before deciding whether another PUT is safe.
                self._snapshot(task, await self.client.detail(task["remote_id"]))
                await self._save(task)
                remote = file["remote"]
                if remote["status"] != "waiting-file" or not remote.get("upload"):
                    return
                if attempt == self.config.max_upload_retries:
                    raise

    async def _download(self, task, file):
        import httpx
        if file["result_path"]:
            return
        for attempt in range(self.config.max_download_retries + 1):
            try:
                payload = await self.client.download(file["remote"])
                directory = self.root / task["id"] / file["id"]
                artifacts = await asyncio.to_thread(store_artifacts, payload, directory, self.config)
                if "default" in self.config.output_formats:
                    normalized = await asyncio.to_thread(normalize_artifacts, task, {**file, "result_path": str(directory)}, artifacts,
                                                         mock=self.config.mode == "mock")
                    await asyncio.to_thread((directory / "normalized.json").write_text, normalized.to_json(), encoding="utf-8")
                    if self.result_sink:
                        file["database_parse_id"] = await asyncio.to_thread(self.result_sink.save, task, file, normalized)
                file["result_path"] = str(directory)
                file.pop("error", None)
                await self._save(task)
                return
            except (httpx.TransportError, MinerUError) as exc:
                if attempt == self.config.max_download_retries or isinstance(exc, MinerUError) and exc.status not in {403, 429, 502, 503, 504}:
                    raise
                # Signed result URLs may be refreshed only through a task snapshot.
                self._snapshot(task, await self.client.detail(task["remote_id"]))
                await self._save(task)

    async def run(self, task_id):
        if task_id in self._locks:
            return
        self._locks[task_id] = True
        started = time.monotonic()
        task = await asyncio.to_thread(self.repository.get, task_id)
        try:
            if task["status"] in TERMINAL:
                return
            if (task["mode"] != self.config.mode or task.get("provider", "self_hosted") != self.config.provider
                    or task["api_identity"] != stable_hash(self.config.api_url) or task["output_formats"] != list(self.config.output_formats)):
                raise MinerUError("resume_configuration_mismatch", 409)
            if bool(task.get('routing_protocol')) != bool(self.dual_router):
                raise MinerUError("resume_configuration_mismatch", 409)
            task["error"] = None
            if task.get("cancel_requested") and not task["remote_id"]:
                task["status"] = "canceled"
                task["completed_at"] = now()
                return
            if self.config.mode == "local":
                await self._local(task)
                return
            for file in task["files"]:
                if await asyncio.to_thread(file_sha256, file["source_path"]) != file["sha256"]:
                    raise MinerUError("source_integrity_mismatch", 409)
            if not task["remote_id"]:
                if task["submission_started"]:
                    raise MinerUError("submission_outcome_unknown", 409)
                task["submission_started"] = True
                await self._save(task)  # crash after POST never causes automatic resubmission
                manifest = [{"file_name": f["file_name"], "bytes": f["bytes"], "sha256sum": f["sha256"]} for f in task["files"]]
                created = await self.client.create(manifest)
                task["remote_id"] = created.get("task_id")
                remote_files = created.get("files", [])
                if not task["remote_id"] or len(remote_files) != len(task["files"]):
                    raise MinerUError("invalid_create_receipt")
                for local, remote in zip(task["files"], remote_files, strict=True):
                    if local["file_name"] != remote.get("file_name") or not remote.get("file_id"):
                        raise MinerUError("file_association_mismatch")
                    local["remote_id"] = remote["file_id"]
                self._snapshot(task, created)
                await self._save(task)  # bind IDs before any PUT
            self.client.bind(task)
            for poll in range(self.config.max_polls):
                current = await asyncio.to_thread(self.repository.get, task_id)
                if current.get("cancel_requested"):
                    if not self.client.supports_cancel:
                        snapshot = await self.client.detail(task["remote_id"])
                        task["cancel_scope"] = "local_only"
                    else:
                        try:
                            snapshot = await self.client.cancel(task["remote_id"])
                        except MinerUError as exc:
                            if exc.status != 409:
                                raise
                            snapshot = await self.client.detail(task["remote_id"])
                else:
                    snapshot = await self.client.detail(task["remote_id"])
                self._snapshot(task, snapshot)
                if task.get("cancel_scope") == "local_only":
                    task["remote_status"] = "canceled"
                await self._save(task)
                for file in task["files"]:
                    if file["status"] == "waiting-file" and not current.get("cancel_requested"):
                        await self._upload(task, file)
                # A queried upload recovery may already expose terminal results.
                for file in task["files"]:
                    if file["status"] == "completed":
                        try:
                            await self._download(task, file)
                        except Exception as exc:
                            file["error"] = {"code": exc.code if isinstance(exc, MinerUError) else type(exc).__name__}
                            file["status"] = "failed"
                            await self._save(task)
                if task["remote_status"] in TERMINAL:
                    if task["remote_status"] == "canceled":
                        task["status"] = "canceled"
                    else:
                        success = sum(bool(f["result_path"]) and not f.get("error") for f in task["files"])
                        task["status"] = "completed" if success == len(task["files"]) else "partial" if success else "failed"
                    task["completed_at"] = now()
                    await self._save(task)
                    return
                if poll + 1 < self.config.max_polls:
                    await asyncio.sleep(self.config.poll_interval)
            task["status"] = "timed_out"
            task["error"] = {"code": "poll_limit"}
        except asyncio.CancelledError:
            # Persist remote IDs and leave task recoverable on next application startup.
            raise
        except Exception as exc:
            task["status"] = "timed_out" if task["remote_id"] else "failed"
            task["error"] = {"code": exc.code if isinstance(exc, MinerUError) else type(exc).__name__}
        finally:
            task["elapsed_seconds"] = round(time.monotonic() - started, 3)
            await self._save(task)
            self._locks.pop(task_id, None)
            logger.info("Parsing task=%s status=%s elapsed=%.3f", task_id, task["status"], task["elapsed_seconds"])

    async def _local(self, task):
        from .document_router import DocumentParser
        from .schemas import DocumentResult
        task["status"] = "running"
        await self._save(task)
        for file in task["files"]:
            if task.get('cancel_requested'):
                task['status'] = 'canceled'
                task['completed_at'] = now()
                return
            if file["status"] == "completed" and file.get("result_path"):
                continue
            file["status"] = "running"
            await self._save(task)
            try:
                if await asyncio.to_thread(file_sha256, file["source_path"]) != file["sha256"]:
                    raise MinerUError("source_integrity_mismatch", 409)
                directory = self.root / task["id"] / file["id"]
                result_path = directory / "normalized.json"
                if file.get("local_result_path"):
                    # Reuse the exact pre-DB result on retry: parsing timestamps
                    # must not change an already committed result's digest.
                    payload = await asyncio.to_thread(result_path.read_text, encoding="utf-8")
                    result = DocumentResult.from_dict(json.loads(payload))
                    if result.document_id != file["sha256"]:
                        raise MinerUError("source_integrity_mismatch", 409)
                else:
                    if self.dual_router:
                        result = await self.dual_router.parse(task, file, self._save)
                        if task.get('cancel_requested'):
                            file['status'] = 'canceled'
                            task['status'] = 'canceled'
                            task['completed_at'] = now()
                            return
                        if await asyncio.to_thread(file_sha256, file['source_path']) != file['sha256']:
                            raise MinerUError('source_integrity_mismatch', 409)
                    else:
                        def parse():
                            with DocumentParser() as parser:
                                return parser.parse(file["source_path"])
                        result = await asyncio.to_thread(parse)
                    if not self.dual_router and result.parsing_status in {"failed", "partial"}:
                        raise MinerUError("local_parse_failed")
                    directory.mkdir(parents=True, exist_ok=True)
                    if self.dual_router:
                        from .dual_engine import persist_result
                        await asyncio.to_thread(persist_result, result_path, result)
                    else:
                        await asyncio.to_thread(result_path.write_text, result.to_json(), encoding="utf-8")
                    file["local_result_path"] = str(directory)
                    await self._save(task)
                if self.dual_router:
                    trace = result.quality['routing_trace']
                    file.update(selected_engine=trace['selected_engine'], requires_review=result.requires_review,
                                fallback_reason=trace.get('failure_reason') or trace['fallback_reason'])
                if result.parsing_status in {"failed", "partial"}:
                    raise MinerUError("local_parse_failed")
                if self.result_sink:
                    file["database_parse_id"] = await asyncio.to_thread(self.result_sink.save, task, file, result)
                file["result_path"] = str(directory)
                file["status"] = "completed"
                file.pop("error", None)
            except Exception as exc:
                file["status"] = "failed"
                file["error"] = {"code": exc.code if isinstance(exc, MinerUError) else type(exc).__name__}
            # A bad parser/file/database result cannot discard sibling progress.
            await self._save(task)
        success = sum(f["status"] == "completed" for f in task["files"])
        task["status"] = "completed" if success == len(task["files"]) else "partial" if success else "failed"
        task["completed_at"] = now()

    async def resume(self, task_id, owner):
        task = await asyncio.to_thread(self.repository.get, task_id, owner)
        if task_id in self._locks:
            raise MinerUError("task_running", 409)
        can_retry_result = any(f.get("remote", {}).get("status") == "completed" and f.get("error") for f in task["files"])
        can_retry_local = task["mode"] == "local" and any(f["status"] == "failed" for f in task["files"])
        if ((task["remote_id"] and (task["status"] == "timed_out" or task["status"] in {"partial", "failed"} and can_retry_result))
                or task["status"] in {"partial", "failed"} and can_retry_local):
            task["status"] = "pending"
            await self._save(task)
        elif task["status"] not in {"created", "pending", "uploading", "running"}:
            raise MinerUError("task_not_resumable", 409)
        return task

    async def cancel(self, task_id, owner):
        task = await asyncio.to_thread(self.repository.get, task_id, owner)
        if task["status"] in TERMINAL:
            return task
        await asyncio.to_thread(self.repository.request_cancel, task_id, owner)
        if task_id not in self._locks:
            await self.run(task_id)
        return await asyncio.to_thread(self.repository.get, task_id, owner)
