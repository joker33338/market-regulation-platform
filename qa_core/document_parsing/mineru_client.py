"""Self-hosted MinerU 4.1 Tasks transport. No implicit create or transfer retries."""
import asyncio
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote, urlsplit

from qa_core.utils import IngestionError
from .mineru_config import MinerUConfig, origin


class MinerUError(IngestionError):
    def __init__(self, code: str, status: int = 502):
        self.code, self.status = code, status
        super().__init__("MinerU operation failed: " + code)


def validate_name(name: str):
    if (not isinstance(name, str) or not 1 <= len(name) <= 1024 or name in {".", ".."}
            or any(char in name for char in "/\\:")
            or any(unicodedata.category(char) == "Cc" for char in name)):
        raise MinerUError("invalid_file_name", 400)


class MinerUClient:
    supports_cancel = True
    def __init__(self, config: MinerUConfig, *, transport=None):
        import httpx
        if config.mode == "mock" and not isinstance(transport, httpx.MockTransport):
            raise MinerUError("mock_transport_required", 400)
        self.config = config
        self.base = (config.api_url or "https://mineru.invalid").rstrip("/")
        self.api_origin = origin(self.base)
        self.allowed = {self.api_origin, *(origin(url) for url in config.allowed_origins)}
        self.http = httpx.AsyncClient(transport=transport, follow_redirects=False, trust_env=False,
                                      timeout=httpx.Timeout(config.request_timeout, connect=config.connect_timeout))

    async def close(self):
        await self.http.aclose()

    async def before_request(self, method, url):
        """Optional policy hook, applied to every HTTP attempt including redirects."""

    def _validate_url(self, url):
        if origin(url) not in self.allowed:
            raise MinerUError("untrusted_origin", 400)
        if urlsplit(url).scheme != "https" and not self.config.allow_http:
            raise MinerUError("insecure_url", 400)

    async def request(self, method, url, *, headers=None, content=None, body=None, max_bytes=1024 * 1024):
        import httpx
        headers = dict(headers or {})
        # Never accept credential-bearing server-supplied transfer headers.
        headers = {k: v for k, v in headers.items() if k.lower() not in {"authorization", "cookie", "host"}}
        if origin(url) == self.api_origin and self.config.api_key:
            headers["Authorization"] = "Bearer " + self.config.api_key
        for _ in range(4):
            self._validate_url(url)
            await self.before_request(method, url)
            async with self.http.stream(method, url, headers=headers, content=content, json=body) as response:
                if response.is_redirect:
                    if method != "GET" or "location" not in response.headers:
                        raise MinerUError("unsafe_redirect")
                    url = str(response.url.join(response.headers["location"]))
                    headers = {}  # do not forward API keys or signed headers on redirects
                    continue
                if response.status_code >= 400:
                    # Retain only the contract's bounded machine-readable code;
                    # messages may echo confidential input or connection details.
                    error_bytes = bytearray()
                    async for block in response.aiter_bytes():
                        error_bytes.extend(block)
                        if len(error_bytes) > 8192:
                            break
                    try:
                        code = json.loads(error_bytes).get("error", {}).get("code", "")
                    except (ValueError, AttributeError):
                        code = ""
                    if not isinstance(code, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", code):
                        code = "http_" + str(response.status_code)
                    raise MinerUError(code, response.status_code)
                payload = bytearray()
                async for block in response.aiter_bytes():
                    payload.extend(block)
                    if len(payload) > max_bytes:
                        raise MinerUError("response_too_large", 413)
                if response.headers.get("content-length") and not response.headers.get("content-encoding"):
                    if int(response.headers["content-length"]) != len(payload):
                        raise MinerUError("incomplete_response")
                return response.status_code, bytes(payload)
        raise MinerUError("redirect_limit")

    async def _json(self, method, route, body=None):
        try:
            status, raw = await self.request(method, self.base + route, body=body)
            value = json.loads(raw)
        except (json.JSONDecodeError, UnicodeError):
            raise MinerUError("invalid_json") from None
        if not isinstance(value, dict):
            raise MinerUError("invalid_response")
        return status, value

    def validate_manifest(self, files):
        if not 1 <= len(files) <= self.config.max_files:
            raise MinerUError("invalid_file_count", 400)
        for file in files:
            if set(file) - {"file_name", "bytes", "sha256sum", "page_range"}:
                raise MinerUError("invalid_manifest", 400)
            validate_name(file.get("file_name"))
            size = file.get("bytes")
            if type(size) is not int or not 0 < size <= self.config.max_file_bytes:
                raise MinerUError("invalid_file_size", 413)

    async def create(self, files):
        self.validate_manifest(files)
        status, result = await self._json("POST", "/v1/tasks", {
            "files": files, "tier": self.config.tier, "output_formats": list(self.config.output_formats)})
        if status != 202:
            raise MinerUError("invalid_create_response")
        return result

    def bind(self, task):
        """Self-hosted Tasks IDs are sufficient to resume without client memory."""

    async def detail(self, task_id):
        return (await self._json("GET", "/v1/tasks/" + quote(task_id, safe="")))[1]

    async def cancel(self, task_id):
        return (await self._json("POST", "/v1/tasks/" + quote(task_id, safe="") + "/cancel"))[1]

    async def health(self):
        return (await self._json("GET", "/v1/health"))[1]

    async def tiers(self):
        return (await self._json("GET", "/v1/tiers"))[1]

    async def upload(self, file: dict, path: Path):
        if file.get("status") != "waiting-file" or not file.get("upload"):
            return False
        target = file["upload"]
        if target.get("expires_at", 0) <= time.time():
            raise MinerUError("upload_expired", 410)

        async def chunks():
            with path.open("rb") as stream:
                while block := await asyncio.to_thread(stream.read, 1024 * 1024):
                    yield block

        await self.request("PUT", target["url"], headers=target["headers"], content=chunks())
        return True

    async def download(self, file):
        _, payload = await self.request("GET", file["result_url"], max_bytes=self.config.max_result_bytes)
        return payload
