"""Official v4 smoke using a generated PDF only. Resume a previously created batch.

The receipt and all results must stay in an ignored local directory. Credentials
are read only from the process environment; never print URLs or server bodies.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import time
from urllib.parse import quote, urlsplit
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def synthetic_pdf():
    text = b"BT /F1 16 Tf 50 760 Td (Synthetic MinerU integration test. No real case data.) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(text)).encode() + b" >>\nstream\n" + text + b"\nendstream"]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def main():
    import httpx
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("reports/official-smoke"))
    parser.add_argument("--verify-client", action="store_true", help="Resume the same batch with the product client; never create another batch")
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))["data"]
    batch = receipt["batch_id"]
    headers = {"Authorization": "Bearer " + os.environ["MINERU_API_KEY"]}
    base = "https://mineru.net/api/v4/extract-results/batch/" + quote(batch, safe="")
    args.output.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
        snapshot = client.get(base, headers=headers)
        snapshot.raise_for_status()
        value = snapshot.json()
        if value.get("code") != 0:
            print(json.dumps({"stage": "query", "api_code": value.get("code")}))
            return 1
        states = [item["state"] for item in value["data"]["extract_result"]]
        if states == ["waiting-file"]:
            url = receipt["file_urls"][0]
            if urlsplit(url).scheme != "https" or urlsplit(url).hostname != "mineru.oss-cn-shanghai.aliyuncs.com":
                raise ValueError("Unapproved upload origin")
            pdf = synthetic_pdf()
            (args.output / "synthetic.pdf").write_bytes(pdf)
            response = client.put(url, content=pdf)  # 此处刻意不附带 API 凭据
            response.raise_for_status()
            print(json.dumps({"stage": "upload", "http_status": response.status_code, "bytes": len(pdf)}), flush=True)
        for attempt in range(60):
            response = client.get(base, headers=headers)
            response.raise_for_status()
            value = response.json()
            (args.output / "snapshot.json").write_text(json.dumps(value), encoding="utf-8")
            if value.get("code") != 0:
                print(json.dumps({"stage": "query", "api_code": value.get("code")}))
                return 1
            files = value["data"]["extract_result"]
            states = [item["state"] for item in files]
            print(json.dumps({"stage": "poll", "attempt": attempt + 1, "states": states}), flush=True)
            if states == ["done"]:
                url = files[0]["full_zip_url"]
                if urlsplit(url).scheme != "https" or urlsplit(url).hostname not in {
                        "cdn-mineru.openxlab.org.cn", "mineru.oss-cn-shanghai.aliyuncs.com"}:
                    raise ValueError("Unapproved result origin")
                with client.stream("GET", url) as download:
                    download.raise_for_status()
                    data = bytearray()
                    for block in download.iter_bytes():
                        data.extend(block)
                        if len(data) > 20 * 1024 * 1024:
                            raise ValueError("Result exceeds smoke budget")
                (args.output / "result.zip").write_bytes(data)
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    names = archive.namelist()
                    summary = {"stage": "complete", "status": "PASS", "files": len(names),
                               "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                               "has_markdown": any(name.endswith(".md") for name in names),
                               "has_json": any(name.endswith(".json") for name in names)}
                (args.output / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
                print(json.dumps(summary))
                if args.verify_client:
                    import asyncio
                    async def verify():
                        from qa_core.document_parsing.mineru_config import MinerUConfig
                        from qa_core.document_parsing.mineru_official import OfficialMinerUClient
                        from qa_core.document_parsing.mineru_repository import TaskRepository
                        from qa_core.document_parsing.mineru_service import MinerUService
                        config = MinerUConfig(enabled=True, mode="remote", provider="official", api_url="https://mineru.net/api",
                                               api_key=os.environ["MINERU_API_KEY"], result_dir=args.output / "product",
                                               poll_interval=2, max_polls=3)
                        remote = files[0]
                        product = OfficialMinerUClient(config)
                        try:
                            service = MinerUService(config, TaskRepository(config.result_dir / "tasks.sqlite3"), product)
                            task, _ = await service.submit("smoke", "official-existing-batch", [("synthetic-smoke.pdf", args.output / "synthetic.pdf")])
                            if task["status"] != "completed":
                                task.update(remote_id=batch, submission_started=True, status="running")
                                task["files"][0].update(remote_id=remote["data_id"], remote={
                                    "file_id": remote["data_id"], "file_name": remote["file_name"], "status": "completed"})
                                service.repository.save(task)
                                await service.run(task["id"])
                            final = service.repository.get(task["id"])
                            print(json.dumps({"stage": "product_client", "status": final["status"], "error": final["error"]}))
                            return 0 if final["status"] == "completed" else 1
                        finally:
                            await product.close()
                    return asyncio.run(verify())
                return 0
            if "failed" in states:
                return 1
            time.sleep(2)
    return 124


if __name__ == "__main__":
    raise SystemExit(main())
