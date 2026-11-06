"""Compatibility entry point: ask(question, stream=True), with richer citations."""
from __future__ import annotations

import json
import os
import urllib.request

from qa_core.config.settings import Settings
from qa_core.retrieval.models import create_embeddings
from qa_core.retrieval.store import retrieve
from qa_core.storage.database import Database
from qa_core.utils import IngestionError


def build_prompt(question: str, hits: list[dict]) -> str:
    references = "\n".join(f"《{hit['law_name']}》{hit['article_no']}（{hit['chapter']}）：{hit['content']}"
                            for hit in hits)
    return ("你是一名法律资料问答助手。仅依据提供的原文回答，逐项标注法律名称和条号。"
            "资料不足时明确说明，不推测法律效力。不得将测试材料作为执法依据。\n"
            f"资料：\n{references}\n问题：{question}")


def ask(question: str, stream: bool = True, *, database: Database | None = None,
        embeddings=None, generate: bool = False) -> dict:
    """Legacy keys remain. Generation is optional; retrieval is fully offline."""
    owned = database is None
    if database is None:
        if os.getenv("PG_DSN"):
            database = Database(pg_dsn=os.environ["PG_DSN"])
        elif os.getenv("LEGAL_SQLITE_PATH"):
            database = Database(sqlite_path=os.environ["LEGAL_SQLITE_PATH"])
        else:
            raise IngestionError("请显式设置 PG_DSN 或 LEGAL_SQLITE_PATH。")
    try:
        embeddings = embeddings or create_embeddings(Settings.from_env())
        hits = retrieve(database, embeddings, question)
        citations = [{
            "law": hit["law_name"], "chapter": hit["chapter"], "article": hit["article_no"],
            "paragraphs": hit["metadata"]["paragraph_nos"], "items": hit["metadata"]["item_nos"],
            "source_spans": hit["metadata"]["source_spans"], "kb_version": hit["kb_version"],
            "chunk_id": hit["chunk_id"], "source": hit["source_path"],
            "doc_version_id": hit["doc_version_id"],
        } for hit in hits]
        answer = "\n\n".join(f"《{hit['law_name']}》{hit['article_no']}：{hit['content']}" for hit in hits)
        mode = "retrieval"
        if generate:
            base, model = os.getenv("API_BASE", "").rstrip("/"), os.getenv("LLM_MODEL", "")
            if not base.startswith(("http://", "https://")) or "@" in base or not model:
                raise IngestionError("生成回答需要显式配置 API_BASE 和 LLM_MODEL。")
            request = urllib.request.Request(base + "/chat/completions", data=json.dumps({
                "model": model, "messages": [{"role": "user", "content": build_prompt(question, hits)}],
                "temperature": 0.1, "stream": False,
            }).encode(), headers={"Content-Type": "application/json",
                                 "Authorization": "Bearer " + os.getenv("API_KEY", "")})
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    answer = json.load(response)["choices"][0]["message"]["content"]
            except Exception:
                raise IngestionError("回答生成失败；未输出服务地址、凭据或响应正文。") from None
            mode = "generated"
        if stream:
            print(answer)
        return {"question": question, "answer": answer, "citations": citations, "mode": mode, "hits": hits}
    finally:
        if owned:
            database.close()

