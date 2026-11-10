"""验证现有官方客户端完整链路；只允许脚本生成的一页合成 PDF，默认不联网。"""
import argparse
import asyncio
from dataclasses import replace
import hashlib
import json
import logging
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qa_core.document_parsing.dual_engine import DualEngineConfig, DualEngineRouter
from qa_core.document_parsing.mineru_config import MinerUConfig
from qa_core.document_parsing.mineru_repository import TaskRepository
from qa_core.document_parsing.mineru_service import MinerUService
from qa_core.document_parsing.schemas import DocumentResult
from qa_core.storage.parsing_results import PostgresResultSink


def synthetic_pdf():
    import fitz
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((60, 80), "SYNTHETIC-MINERU-V021", fontsize=18)
        page.insert_text((60, 120), "This generated page verifies an authorized cloud parsing workflow.", fontsize=11)
        page.insert_text((60, 145), "It contains no case material, personal data or confidential information.", fontsize=11)
        return document.tobytes(no_new_id=True, garbage=4, deflate=True)


def prepare(output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    payload = synthetic_pdf()
    path = output / "synthetic-mineru-smoke.pdf"
    if path.exists() and path.read_bytes() != payload:
        raise ValueError("已有验证文件不匹配固定合成内容，拒绝覆盖或上传。")
    if not path.exists():
        path.write_bytes(payload)
    return path, hashlib.sha256(payload).hexdigest()


async def verify(args):
    source, sha = prepare(args.output)
    if not args.execute:
        return dict(status="DRY_RUN", input_sha256=sha, pages=1, cloud_requests=0)
    values = json.loads(args.config.read_text(encoding="utf-8-sig"))
    if not values.get("MINERU_API_KEY"):
        raise ValueError("未配置官方 API Token。")
    owner = next(iter(json.loads(values["PARSING_API_TOKENS_JSON"]).values()))
    approval_file = args.output / "synthetic-authorization.json"
    if not approval_file.exists():
        approval_file.write_text(json.dumps(dict(sha256=sha, owner=owner, expires_at=time.time()+3600,
                                                 authorization_id="user-request-synthetic-mineru-v021")), encoding="utf-8")
    approval = json.loads(approval_file.read_text(encoding="utf-8"))
    if approval["sha256"] != sha or approval["owner"] != owner or approval["expires_at"] <= time.time():
        raise ValueError("合成验证授权不匹配或过期；保留已有账本，不自动续期。")
    remote = MinerUConfig(enabled=True, mode="remote", provider="official", api_url="https://mineru.net/api",
                         api_key=values["MINERU_API_KEY"], result_dir=args.output, poll_interval=20,
                         max_polls=5, connect_timeout=5, request_timeout=30,
                         max_files=1, max_upload_retries=0, max_download_retries=0)
    policy = DualEngineConfig(enabled=True, cloud_enabled=True, max_cloud_calls=8, max_task_calls=8,
                              max_cloud_files=1, max_cloud_pages=1)
    router = DualEngineRouter(policy, remote, grants={owner: {sha: approval}})
    service = MinerUService(replace(remote, mode="local", provider="self_hosted", api_url=""),
                           TaskRepository(args.output / "tasks.sqlite3"), dual_router=router)
    task, created = await service.submit(owner, "synthetic-cloud-smoke-"+sha, [(source.name, source)],
        parse_options=dict(strategy="remote", allow_cloud_fallback=True, sensitive=False))
    await service.run(task["id"])
    task = service.repository.get(task["id"], owner)
    file = task["files"][0]
    result = None
    trace = {}
    if file.get("result_path"):
        result = DocumentResult.from_dict(json.loads((Path(file["result_path"])/"normalized.json").read_text(encoding="utf-8")))
        trace = result.quality.get("routing_trace", {})
    passed = (task["status"] == "completed" and trace.get("selected_engine") == ["mineru_official"]
              and trace.get("remote_task_id") and not trace.get("failure_reason")
              and bool(result and result.raw_text.strip()))
    if passed and args.database:
        sink = PostgresResultSink(values["PARSING_RESULT_PG_DSN"])
        file["database_parse_id"] = await asyncio.to_thread(sink.save, task, file, result)
        await service._save(task)
    summary = dict(status="PASS" if passed else "FAILED", created=created, input_sha256=sha,
                   task_id=task["id"], remote_task_id=trace.get("remote_task_id"),
                   selected_engine=trace.get("selected_engine"), failure_reason=trace.get("failure_reason") or
                   (file.get("error") or task.get("error") or {}).get("code"),
                   usage=trace.get("usage", file.get("routing_state", {})),
                   local_candidate_preserved="local" in trace.get("raw_results", {}),
                   remote_candidate_preserved="remote" in trace.get("raw_results", {}),
                   result_characters=len(result.raw_text) if result else 0,
                   requires_review=result.requires_review if result else True,
                   database_parse_id=file.get("database_parse_id"), source_unchanged=source.read_bytes()==synthetic_pdf())
    (args.output/"verification.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/private/runtime.json"))
    parser.add_argument("--output", type=Path, default=Path("/state/mineru-synthetic-check"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--database", action="store_true")
    args = parser.parse_args()
    args.output = args.output.resolve()
    # 探针只可写部署状态目录或本项目的忽略目录，不接受真实资料输入。
    if not (args.output.is_relative_to(Path("/state")) or args.output.is_relative_to(ROOT / "local")):
        parser.error("验证输出必须位于 /state 或项目忽略的 local 目录。")
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    try:
        result = asyncio.run(verify(args))
    except Exception as exc:
        result = dict(status="FAILED", error_type=type(exc).__name__, error_code=getattr(exc, "code", None))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] in {"PASS", "DRY_RUN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
