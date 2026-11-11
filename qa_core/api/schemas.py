"""新增 HTTP 契约；旧解析接口的响应字段保持原样。"""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ListResponse(BaseModel):
    list: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    source: str


class DocumentInfo(BaseModel):
    file_id: str
    file_name: str
    doc_type: str
    size_bytes: int
    sha256: str
    uploaded_at: str
    uploaded_at_source: str
    status: str
    latest_task_id: str | None
    parse_count: int


class DocumentList(ListResponse):
    list: list[DocumentInfo]


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_type: Literal["law", "case"]
    max_chars: int = Field(default=800, ge=64, le=1600)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=2000)
    mode: Literal["keyword", "hybrid"] = "keyword"
    limit: int = Field(default=8, ge=1, le=50)


class SearchResponse(BaseModel):
    status: Literal["ready", "unpublished"]
    kb_version: str | None
    mode: str
    list: list[dict[str, Any]]
    count: int
    source: str = "public"


class ReviewDetail(BaseModel):
    parse_id: str
    document_id: str
    file_name: str
    parsing_status: str
    requires_review: bool
    source_location: dict[str, Any]
    quality: dict[str, Any]
    raw_text: str
    markdown_content: str
    original_result: dict[str, Any]
    source_file_id: str | None = None
    task_id: str | None = None
    local_candidate: dict[str, Any] | None = None
    local_candidate_available: bool = False
    review_write_supported: bool = False


class PreviewResponse(BaseModel):
    preview: dict[str, Any]
    write_performed: bool = False


class StatsResponse(BaseModel):
    generated_at: str
    window: dict[str, Any]
    uploads: dict[str, Any]
    tasks: dict[str, Any]
    parsed_documents: dict[str, Any]
    recent_tasks: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    components: dict[str, dict[str, Any]]


class VersionInfo(BaseModel):
    kb_version: str
    status: str
    active: bool
    dimension: int
    created_at: str
    stats: dict[str, Any] | str
