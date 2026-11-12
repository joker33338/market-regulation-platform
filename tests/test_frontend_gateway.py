"""仅使用合成静态文件与模拟上游验证前端部署网关。"""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient


class FrontendGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / "dist" / "assets").mkdir(parents=True)
        (root / "dist" / "index.html").write_text("<html>synthetic app</html>", encoding="utf-8")
        (root / "dist" / "assets" / "test.js").write_text("export default 1", encoding="utf-8")
        shutil.copyfile(Path(__file__).resolve().parents[1] / "deploy/frontend/server.py", root / "server.py")
        spec = importlib.util.spec_from_file_location("frontend_gateway_test", root / "server.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_pages_resources_and_missing_assets(self):
        with TestClient(self.module.app) as client:
            for path in ("/", "/dashboard", "/documents", "/parsing", "/review", "/knowledge/ingestion", "/knowledge/search", "/system"):
                response = client.get(path)
                self.assertEqual(response.status_code, 200, path)
                self.assertIn("synthetic app", response.text)
                self.assertEqual(response.headers["cache-control"], "no-cache")
            self.assertEqual(client.get("/assets/missing.js").status_code, 404)
            self.assertEqual(client.get("/assets/test.js").status_code, 200)
            self.assertEqual(client.get("/healthz").status_code, 200)

    def test_proxy_preserves_auth_query_body_range_and_errors(self):
        seen = []

        class Body(httpx.AsyncByteStream):
            def __init__(self, value):
                self.value = value

            async def __aiter__(self):
                yield self.value

        def handler(request):
            seen.append(request)
            if request.method == "POST":
                return httpx.Response(202, stream=Body(b'{"accepted":true}'))
            if "authorization" not in request.headers:
                return httpx.Response(401, stream=Body(b'{"error":{"code":"unauthorized"}}'))
            return httpx.Response(206, stream=Body(b"part"), headers={"Content-Range": "bytes 0-3/10"})

        original = httpx.AsyncClient
        with patch.object(self.module.httpx, "AsyncClient", side_effect=lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)):
            with TestClient(self.module.app) as client:
                self.assertEqual(client.get("/api/parse/info").status_code, 401)
                response = client.get("/api/files/source?name=sample%20file", headers={"Authorization": "Bearer synthetic", "Range": "bytes=0-3"})
                self.assertEqual(response.status_code, 206)
                self.assertEqual(response.content, b"part")
                self.assertEqual(response.headers["content-range"], "bytes 0-3/10")
                self.assertEqual(seen[-1].headers["authorization"], "Bearer synthetic")
                self.assertEqual(seen[-1].headers["range"], "bytes=0-3")
                self.assertEqual(seen[-1].url.host, "market-regulation-app-1")
                self.assertEqual(seen[-1].url.params["name"], "sample file")
                self.assertEqual(client.post("/api/parse/files", content=b"synthetic bytes").status_code, 202)
                self.assertEqual(seen[-1].content, b"synthetic bytes")


if __name__ == "__main__":
    unittest.main()
