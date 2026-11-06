"""Application-side remote parser configuration; never imports model runtimes."""
from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit

from qa_core.utils import IngestionError


def origin(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username
            or parsed.password or parsed.fragment):
        raise IngestionError("MinerU URL must be HTTP(S), without credentials or fragments.")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        raise IngestionError("Invalid MinerU URL port.") from None
    return f"{parsed.scheme}://{parsed.hostname.lower()}:{port}"


@dataclass(frozen=True)
class MinerUConfig:
    enabled: bool = False
    mode: str = "mock"
    provider: str = "self_hosted"
    cloud_model: str = "vlm"
    api_url: str = ""
    api_key: str = field(default="", repr=False)
    tier: str = "standard"
    parser_version: str = "4.1.7"
    connect_timeout: float = 5
    request_timeout: float = 60
    poll_interval: float = 2
    max_polls: int = 150
    max_upload_retries: int = 2
    max_download_retries: int = 2
    output_formats: tuple[str, ...] = ("default",)
    result_dir: Path = Path("local/mineru")
    allowed_origins: tuple[str, ...] = ()
    allow_http: bool = False
    max_file_bytes: int = 100 * 1024 * 1024
    max_result_bytes: int = 100 * 1024 * 1024
    max_expanded_bytes: int = 200 * 1024 * 1024
    max_members: int = 2000
    max_files: int = 20
    concurrency: int = 1
    queue_size: int = 20

    def __post_init__(self):
        if self.provider not in {"self_hosted", "official"} or self.cloud_model not in {"vlm", "pipeline"}:
            raise IngestionError("Unknown MinerU provider or cloud model.")
        if self.provider == "official" and (self.api_url.rstrip("/") != "https://mineru.net/api" or "default" not in self.output_formats):
            raise IngestionError("Official provider requires https://mineru.net/api and default artifacts.")
        if self.mode not in {"mock", "remote", "local"} or self.tier != "standard":
            raise IngestionError("Parser mode must be mock/remote/local; remote tier must be standard.")
        if self.mode == "remote" and not self.api_url:
            raise IngestionError("Remote MinerU requires MINERU_API_URL.")
        if self.api_url:
            origin(self.api_url)
            if urlsplit(self.api_url).query:
                raise IngestionError("MinerU API base cannot contain a query.")
            if urlsplit(self.api_url).scheme != "https" and not self.allow_http:
                raise IngestionError("HTTP requires explicit private-network opt-in.")
        for url in self.allowed_origins:
            origin(url)
        if not self.output_formats or not set(self.output_formats) <= {"default", "docx", "html", "latex"}:
            raise IngestionError("Unsupported MinerU output format.")
        limits = (self.connect_timeout, self.request_timeout, self.max_polls, self.max_file_bytes,
                  self.max_result_bytes, self.max_expanded_bytes, self.max_members, self.max_files,
                  self.concurrency, self.queue_size)
        if min(limits) <= 0 or self.poll_interval < 0 or min(self.max_upload_retries, self.max_download_retries) < 0:
            raise IngestionError("MinerU resource limits are invalid.")

    @classmethod
    def from_env(cls):
        values = {}
        for name in ("mode", "provider", "cloud_model", "api_url", "api_key", "tier"):
            if "MINERU_" + name.upper() in os.environ:
                values[name] = os.environ["MINERU_" + name.upper()]
        for name in ("connect_timeout", "request_timeout", "poll_interval"):
            if "MINERU_" + name.upper() in os.environ:
                values[name] = float(os.environ["MINERU_" + name.upper()])
        for name in ("max_polls", "max_upload_retries", "max_download_retries", "max_file_bytes",
                     "max_result_bytes", "max_expanded_bytes", "concurrency", "queue_size"):
            if "MINERU_" + name.upper() in os.environ:
                values[name] = int(os.environ["MINERU_" + name.upper()])
        values["enabled"] = os.getenv("MINERU_ENABLED", "0") == "1"
        values["allow_http"] = os.getenv("MINERU_ALLOW_HTTP", "0") == "1"
        values["result_dir"] = Path(os.getenv("MINERU_RESULT_DIR", "local/mineru"))
        values["output_formats"] = tuple(os.getenv("MINERU_OUTPUT_FORMATS", "default").split(","))
        values["allowed_origins"] = tuple(filter(None, os.getenv("MINERU_ALLOWED_ORIGINS", "").split(",")))
        if values.get("provider") == "official" and not values.get("api_url"):
            values["api_url"] = "https://mineru.net/api"
        if not values.get("api_key") and os.getenv("MINERU_TOKEN"):
            values["api_key"] = os.environ["MINERU_TOKEN"]
        return cls(**values)
