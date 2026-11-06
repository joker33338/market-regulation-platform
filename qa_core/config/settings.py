"""Independent configuration; never imports the old project's .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "legal-structure-mvp-v1"
CLEANER_VERSION = "conservative-v1"


@dataclass(frozen=True)
class Settings:
    embedding_backend: str = "local"
    embedding_model_path: Path = ROOT / "models" / "bge-m3"
    embedding_dimension: int = 1024
    embedding_max_tokens: int = 2048
    max_chunk_chars: int = 800
    batch_size: int = 8

    def __post_init__(self):
        from qa_core.utils import IngestionError
        if not 1 <= self.embedding_dimension <= 4096:
            raise IngestionError("Embedding 维度必须在 1–4096 之间。")
        if self.embedding_max_tokens < 32 or self.max_chunk_chars < 64:
            raise IngestionError("token 预算至少为 32，字符上限至少为 64。")
        if not 1 <= self.batch_size <= 128:
            raise IngestionError("批次大小必须在 1–128 之间。")

    @classmethod
    def from_env(cls) -> "Settings":
        path = Path(os.getenv("EMBEDDING_MODEL_PATH", "models/bge-m3"))
        return cls(
            embedding_backend=os.getenv("EMBEDDING_BACKEND", "local"),
            embedding_model_path=path if path.is_absolute() else ROOT / path,
            embedding_dimension=int(os.getenv("EMBEDDING_DIMENSION", "1024")),
            embedding_max_tokens=int(os.getenv("EMBEDDING_MAX_TOKENS", "2048")),
        )

