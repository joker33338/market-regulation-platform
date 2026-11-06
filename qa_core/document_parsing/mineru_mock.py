"""Explicit synthetic Tasks server for development only; never parses user bytes."""
import io
import json
from urllib.parse import unquote
from uuid import uuid4
import zipfile


def mock_transport():
    import httpx
    tasks = {}

    def handler(request):
        path = unquote(request.url.path)
        if path.endswith(("/v1/health", "/v1/tiers")):
            return httpx.Response(200, json={"mock": True, "tier": "standard"})
        if path.endswith("/v1/tasks") and request.method == "POST":
            body = json.loads(request.content)
            tid = uuid4().hex
            files = [{"file_id": uuid4().hex, "file_name": item["file_name"], "status": "waiting-file"} for item in body["files"]]
            for file in files:
                file["upload"] = {"url": f"https://mineru.invalid/input/{tid}/{file['file_id']}", "headers": {}, "expires_at": 4102444800}
            tasks[tid] = {"task_id": tid, "status": "waiting-file", "files": files}
            return httpx.Response(202, json=tasks[tid])
        if request.method == "PUT":
            tid, fid = path.split("/")[-2:]
            for file in tasks[tid]["files"]:
                if file["file_id"] == fid:
                    file.update(status="completed", result_url="https://mineru.invalid/result/" + fid,
                                parse={"tier": "standard", "parser_version": "mock-4.1.7"})
                    file.pop("upload", None)
            tasks[tid]["status"] = "completed" if all(f["status"] == "completed" for f in tasks[tid]["files"]) else "waiting-file"
            return httpx.Response(200, json={"task_id": tid, "file_id": fid, "status": "completed"})
        if "/result/" in path:
            text = "第一条 这是 Mock 合成产物，不是文件识别结果。"
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("markdown.md", text)
                archive.writestr("structured_content.json", json.dumps({"pages": [{"page_idx": 0, "blocks": [{"type": "text", "content": text}]}]}))
                archive.writestr("middle_json.json", json.dumps({"schema": "docvortex.middle", "schema_version": "2.0", "pages": []}))
            return httpx.Response(200, content=buffer.getvalue())
        tid = path.split("/")[-2] if path.endswith("/cancel") else path.split("/")[-1]
        if tid not in tasks:
            return httpx.Response(404, json={"error": {"code": "task_not_found", "message": "Mock task missing"}})
        if path.endswith("/cancel"):
            tasks[tid]["status"] = "canceled"
            for file in tasks[tid]["files"]:
                if file["status"] != "completed":
                    file["status"] = "canceled"
        return httpx.Response(200, json=tasks[tid])
    return httpx.MockTransport(handler)
