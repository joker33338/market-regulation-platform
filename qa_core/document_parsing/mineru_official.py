"""Official public v4 API adapter, distinct from the self-hosted 4.1 Tasks API.

Contract: https://mineru.net/apiManage/docs. Public data_id is a caller association,
not a self-hosted server file_id. No undocumented public cancellation is attempted.
"""
import time
from urllib.parse import quote
from uuid import uuid4

from .mineru_client import MinerUClient, MinerUError
from .mineru_config import origin


class OfficialMinerUClient(MinerUClient):
    supports_cancel = False

    def __init__(self, config, *, transport=None):
        super().__init__(config, transport=transport)
        self.allowed.update(origin(url) for url in (
            "https://mineru.oss-cn-shanghai.aliyuncs.com", "https://cdn-mineru.openxlab.org.cn"))
        self.bindings = {}

    async def _data(self, method, route, body=None):
        _, result = await self._json(method, route, body)
        if result.get("code") != 0:
            code = result.get("code")
            raise MinerUError("official_api_" + (str(code) if type(code) is int else "invalid_response"))
        if not isinstance(result.get("data"), dict):
            raise MinerUError("invalid_official_response")
        return result["data"]

    async def create(self, files):
        self.validate_manifest(files)
        bindings = [{"file_id": uuid4().hex, "file_name": file["file_name"], "status": "waiting-file"} for file in files]
        data = await self._data("POST", "/v4/file-urls/batch", {
            "files": [{"name": file["file_name"], "data_id": file["file_id"]} for file in bindings],
            "model_version": self.config.cloud_model,
            "extra_formats": [fmt for fmt in self.config.output_formats if fmt != "default"]})
        urls = data.get("file_urls", [])
        if not data.get("batch_id") or len(urls) != len(bindings):
            raise MinerUError("invalid_official_receipt")
        for file, url in zip(bindings, urls, strict=True):
            self._validate_url(url)
            file["upload"] = {"url": url, "headers": {}, "expires_at": int(time.time()) + 86400}
            file["identity_kind"] = "official_data_id"
        tid = data["batch_id"]
        self.bindings[tid] = bindings
        return {"task_id": tid, "status": "waiting-file", "files": bindings}

    def bind(self, task):
        if task["remote_id"]:
            self.bindings[task["remote_id"]] = [file["remote"] for file in task["files"]]

    async def detail(self, task_id):
        data = await self._data("GET", "/v4/extract-results/batch/" + quote(task_id, safe=""))
        if data.get("batch_id") != task_id or task_id not in self.bindings:
            raise MinerUError("official_association_missing")
        bindings = {file["file_id"]: file for file in self.bindings[task_id]}
        files = []
        mapping = {"done": "completed", "failed": "failed", "pending": "pending",
                   "waiting-file": "waiting-file", "running": "running", "converting": "running"}
        for item in data.get("extract_result", []):
            fid = item.get("data_id")
            if fid not in bindings or item.get("state") not in mapping:
                raise MinerUError("official_file_association_mismatch")
            original = bindings[fid]
            file = {"file_id": fid, "file_name": item["file_name"], "status": mapping[item["state"]],
                    "identity_kind": "official_data_id"}
            if file["file_name"] != original["file_name"]:
                raise MinerUError("official_file_association_mismatch")
            if file["status"] == "waiting-file" and original.get("upload"):
                file["upload"] = original["upload"]
            if file["status"] == "completed":
                file["result_url"] = item["full_zip_url"]
                file["parse"] = {"provider": "official", "model_version": self.config.cloud_model}
            elif file["status"] == "failed":
                file["error"] = {"code": "official_parse_failed"}
            files.append(file)
        statuses = [file["status"] for file in files]
        terminal = statuses and all(status in {"completed", "failed"} for status in statuses)
        status = ("completed" if all(s == "completed" for s in statuses) else "failed" if all(s == "failed" for s in statuses) else "partial") if terminal else "running" if "running" in statuses else "waiting-file" if "waiting-file" in statuses else "pending"
        return {"task_id": task_id, "status": status, "files": files}

    async def cancel(self, task_id):
        raise MinerUError("official_cancel_not_supported", 409)
