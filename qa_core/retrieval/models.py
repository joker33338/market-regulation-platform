"""Local BGE by default; HTTP and explicitly labelled demo providers are optional."""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from qa_core.config.settings import Settings
from qa_core.utils import IngestionError, stable_hash


def validate_vectors(vectors: list, count: int, dimension: int) -> list[list[float]]:
    if not isinstance(vectors, list) or len(vectors) != count:
        raise IngestionError("Embedding 返回数量与输入数量不一致。")
    result = []
    for vector in vectors:
        if not isinstance(vector, (list, tuple)) or len(vector) != dimension:
            raise IngestionError("Embedding 维度不符合配置。")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector):
            raise IngestionError("Embedding 包含非法数值。")
        if not any(v != 0 for v in vector):
            raise IngestionError("Embedding 返回零向量。")
        result.append([float(v) for v in vector])
    return result


class LocalEmbeddings:
    def __init__(self, settings: Settings):
        self.dimension = settings.embedding_dimension
        self.path = settings.embedding_model_path
        self.max_tokens = settings.embedding_max_tokens
        manifest_path = self.path.parent / "model_manifest.json"
        if not manifest_path.is_file():
            raise IngestionError("离线模型尚未校验；请先运行 scripts/verify_models.py。")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("model") != self.path.name:
            raise IngestionError("模型清单与配置路径不匹配。")
        for entry in manifest["files"]:
            item = self.path / entry["path"]
            if not item.is_file() or item.stat().st_size != entry["bytes"]:
                raise IngestionError("离线模型文件缺失或大小与校验清单不一致。")
        self.signature = stable_hash("local-bge-normalized-v1", manifest["files"], self.max_tokens, self.dimension)
        self._model = None

    def _load(self):
        if self._model is None:
            # Set before importing model libraries; no network fallback is allowed.
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(str(self.path), device="cpu", local_files_only=True)
            except ImportError as exc:
                raise IngestionError("本地向量化依赖未安装，请按 README 安装 requirements-local.txt。") from exc
            self._model.max_seq_length = self.max_tokens
            actual = self._model.get_sentence_embedding_dimension()
            if actual != self.dimension:
                raise IngestionError("本地模型维度与配置不匹配。")
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        for text in texts:
            if len(model.tokenizer.encode(text, add_special_tokens=True, truncation=False)) > self.max_tokens:
                raise IngestionError("片段超过模型 token 预算，请降低 --max-chars 后重新构建；未静默截断。")
        values = model.encode(texts, batch_size=min(8, len(texts)), normalize_embeddings=True,
                              show_progress_bar=False).tolist()
        return validate_vectors(values, len(texts), self.dimension)


class HTTPEmbeddings:
    def __init__(self, *, base_url: str, api_key: str, model: str, dimension: int = 1024, retries: int = 2):
        if not base_url.startswith(("http://", "https://")) or "@" in base_url:
            raise IngestionError("API_BASE 必须是无内嵌凭据的 HTTP(S) 地址。")
        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model
        self.dimension, self.retries = dimension, retries
        self.signature = stable_hash("http-embedding-v1", self.base_url, model, dimension,
                                     os.getenv("EMBEDDING_MODEL_VERSION", model))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        request = urllib.request.Request(
            self.base_url + "/embeddings",
            data=json.dumps({"model": self.model, "input": texts}).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key},
        )
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    data = json.load(response)["data"]
                if len(data) != len(texts) or sorted(item["index"] for item in data) != list(range(len(texts))):
                    raise IngestionError("Embedding 响应 index 不完整或重复。")
                return validate_vectors([item["embedding"] for item in sorted(data, key=lambda item: item["index"])],
                                        len(texts), self.dimension)
            except urllib.error.HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == self.retries:
                    raise IngestionError("Embedding 服务请求失败；未输出连接信息或响应正文。") from None
            except (TimeoutError, urllib.error.URLError):
                if attempt == self.retries:
                    raise IngestionError("Embedding 服务超时或无法连接。") from None
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise IngestionError("Embedding 服务返回格式不正确。") from exc
            time.sleep(min(2 ** attempt, 4))
        raise IngestionError("Embedding 请求失败。")


class DemoEmbeddings:
    """Deterministic character hashing for pipeline tests, never a semantic model."""
    def __init__(self, dimension: int = 32):
        self.dimension = dimension
        self.signature = stable_hash("DEMO-character-hash-v1", dimension)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        values = []
        for text in texts:
            vector = [0.0] * self.dimension
            for char in text:
                index = int.from_bytes(hashlib.sha256(char.encode()).digest()[:4], "big") % self.dimension
                vector[index] += 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            values.append([value / norm for value in vector])
        return validate_vectors(values, len(texts), self.dimension)


def create_embeddings(settings: Settings):
    if settings.embedding_backend == "local":
        return LocalEmbeddings(settings)
    if settings.embedding_backend == "http":
        return HTTPEmbeddings(base_url=os.getenv("API_BASE", ""), api_key=os.getenv("API_KEY", ""),
                              model=os.getenv("EMBED_MODEL", "bge-m3-mlx-8bit"),
                              dimension=settings.embedding_dimension)
    if settings.embedding_backend == "demo":
        return DemoEmbeddings(settings.embedding_dimension)
    raise IngestionError("未知 Embedding backend。")

