"""工作台接口的公开响应模型；不公开私密操作快照与文件系统位置。"""
from typing import Any, Literal

from pydantic import BaseModel, Field

from .schemas import DocumentInfo, ListResponse


class StoreAvailability(BaseModel):
    postgres: bool
    review_ledger: bool


class UploadBatchOption(BaseModel):
    batch_id: str
    name: str
    count: int


class WorkbenchDocument(DocumentInfo):
    title: str
    number: str | None = None
    category: Literal["law", "case", "unconfirmed"]
    stage: Literal["uploaded", "processing", "awaiting_review", "awaiting_classification", "ready_to_build",
                   "awaiting_publish", "published", "needs_attention", "state_unavailable"]
    parse_id: str | None = None
    review_version: int | None = None
    blocked_reason: str | None = None
    child_document_count: int = 0
    published_document_count: int = 0
    relative_path: str = ""
    batch_ids: list[str] = Field(default_factory=list)


class WorkbenchPage(ListResponse):
    list: list[WorkbenchDocument]
    summary: dict[str, int]
    availability: StoreAvailability
    batches: list[UploadBatchOption]


class BatchFileStatus(BaseModel):
    file_id: str
    file_name: str | None = None
    relative_path: str = ""
    status: Literal["queued", "dispatching", "submitted", "parsed", "failed", "duplicate"]
    task_id: str | None = None
    error_code: str | None = None
    parse_id: str | None = None
    duplicate_of: str | None = None


class UploadBatchStatus(BaseModel):
    operation_id: str
    name: str
    created_at: str
    files: list[BatchFileStatus]
    total_files: int
    counts: dict[str, int]


class UploadBatchPage(ListResponse):
    list: list[UploadBatchStatus]


class SelectionSnapshot(BaseModel):
    selection_id: str
    count: int
    expires_at: float


class SelectionFile(BaseModel):
    file_id: str
    file_name: str
    sha256: str
    parse_id: str | None = None
    review_version: int | None = None


class SelectionFilePage(ListResponse):
    list: list[SelectionFile]


class KnowledgeJobStatus(BaseModel):
    job_id: str
    file_id: str
    title: str
    document_type: Literal["law", "case"]
    status: Literal["queued", "awaiting_parse", "awaiting_review", "awaiting_admin",
                    "building", "awaiting_publish", "published", "needs_attention", "superseded"]
    created_at: str
    updated_at: str | None = None
    error_code: str | None = None
    kb_version: str
    published_version: str | None = None


class KnowledgeJobPage(ListResponse):
    list: list[KnowledgeJobStatus]


class ReviewBatchStatus(BaseModel):
    batch_id: str
    action: Literal["approve", "reject"]
    total: int
    counts: dict[str, int]


class ReviewBatchItem(BaseModel):
    file_id: str
    file_name: str | None = None
    status: Literal["queued", "running", "completed", "failed"]
    error_code: str | None = None


class ReviewBatchItemPage(ListResponse):
    list: list[ReviewBatchItem]


class SourceSegment(BaseModel):
    title: str
    document_type: Literal["law", "case"]
    start: int
    end: int
    expected_text_sha256: str
    requires_confirmation: Literal[True]
    page_start: int
    page_end: int


class SourceSuggestions(BaseModel):
    file_id: str
    source_parse_id: str
    expected_sha256: str
    suggested_type: Literal["law", "case"] | None
    requires_confirmation: Literal[True]
    text_sha256: str
    source_text: str
    text_start: int
    total_characters: int
    page_offset: int
    segments: list[SourceSegment]
    warning: str


class ReviewedPage(BaseModel):
    page_number: int
    text: str


class ReviewedText(BaseModel):
    parse_id: str
    review_version: int
    approved: bool
    original_unchanged: Literal[True]
    pages: list[ReviewedPage]
    revisions: list[dict[str, Any]]


class ReviewQueueRow(BaseModel):
    parse_id: str
    document_id: str
    file_name: str
    file_type: str
    parsing_status: str
    requires_review: bool
    imported_at: Any
    source_location: dict[str, str | None]
    quality: dict[str, Any]


class WorkbenchReviewQueue(ListResponse):
    list: list[ReviewQueueRow]
