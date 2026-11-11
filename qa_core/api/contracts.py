"""补充旧接口 OpenAPI 描述，不改变其既有请求处理或响应序列化行为。"""
from .schemas import ParseInfo, ParseTask, TaskResults, UploadReceipt


def annotate_legacy(app):
    descriptions = {
        ("GET", "/api/parse/info"): (200, ParseInfo),
        ("POST", "/api/parse/files"): (201, UploadReceipt),
        ("POST", "/api/parse/tasks"): (202, ParseTask),
        ("GET", "/api/parse/tasks/{task_id}"): (200, ParseTask),
        ("GET", "/api/parse/tasks/{task_id}/errors"): (200, ParseTask),
        ("POST", "/api/parse/tasks/{task_id}/resume"): (202, ParseTask),
        ("POST", "/api/parse/tasks/{task_id}/cancel"): (200, ParseTask),
        ("GET", "/api/parse/tasks/{task_id}/results"): (200, TaskResults),
    }
    definitions = {}
    for route in app.routes:
        for method in getattr(route, "methods", ()):
            item = descriptions.get((method, route.path))
            if not item:
                continue
            status, model = item
            schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
            definitions.update(schema.pop("$defs", {}))
            extra = {"responses": {str(status): {"content": {"application/json": {"schema": schema}}}}}
            if (method, route.path) == ("POST", "/api/parse/files"):
                extra["requestBody"] = {"required": True, "content": {
                    "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}}
            if (method, route.path) == ("POST", "/api/parse/tasks"):
                extra["parameters"] = [{"name": "Idempotency-Key", "in": "header", "required": True,
                                        "schema": {"type": "string", "minLength": 1, "maxLength": 128}}]
                extra["requestBody"] = {"required": True, "content": {"application/json": {"schema": {
                    "type": "object", "additionalProperties": False, "required": ["file_ids"], "properties": {
                        "file_ids": {"type": "array", "minItems": 1, "maxItems": 20,
                                     "items": {"type": "string", "pattern": "^[0-9a-f]{32}$"}},
                        "strategy": {"type": "string", "enum": ["auto", "local", "remote"]},
                        "allow_cloud_fallback": {"type": "boolean"}, "sensitive": {"type": "boolean"}}}}}}
            route.openapi_extra = extra
    for route in app.routes:
        if not getattr(route, "path", "").startswith("/api/"):
            continue
        extra = route.openapi_extra or {}
        responses = extra.setdefault("responses", {})
        for status in (401, 404, 409, 429, 503):
            responses.setdefault(str(status), {"description": "认证、权限、门禁、限流或服务不可用",
                "content": {"application/json": {"schema": {"type": "object", "properties": {
                    "error": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
                    "required": ["error"]}}}})
        if route.path.endswith("/source"):
            responses.update({"200": {"description": "认证后读取原始文件", "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
                "headers": {"X-SHA256": {"schema": {"type": "string"}},
                            "Accept-Ranges": {"schema": {"type": "string"}}}},
                              "206": {"description": "原始文件字节范围"}, "416": {"description": "范围无效"}})
        route.openapi_extra = extra
    default_openapi = app.openapi

    def openapi():
        schema = default_openapi()
        schema.setdefault("components", {}).setdefault("schemas", {}).update(definitions)
        schema["info"]["version"] = "0.2.2-api-candidate"
        return schema
    app.openapi = openapi
