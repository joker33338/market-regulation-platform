"""正式部署入口：保留业务 API，以最终 Vue 构建提供根路径。"""
from pathlib import Path
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles
from qa_core.document_parsing.mineru_api import create_app as business_app


class VueFiles(StaticFiles):
    async def get_response(self, path, scope):
        if path == "api" or path.startswith("api/"):
            return JSONResponse({"error": {"code": "not_found"}}, status_code=404)
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or path.startswith("assets/") or Path(path).suffix:
                raise
            response = FileResponse(Path(self.directory) / "index.html")
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def create_app():
    app = business_app()
    # 只在部署适配层替换旧根路径，不修改OCR、认证及任务业务实现。
    app.router.routes[:] = [route for route in app.router.routes if getattr(route, "path", None) != "/"]
    app.mount("/", VueFiles(directory="/app/frontend/dist", html=True), name="vue")
    return app
