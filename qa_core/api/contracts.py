"""补充旧接口 OpenAPI 描述，不改变其既有请求处理或响应序列化行为。"""
from .schemas import ParseInfo, ParseTask, TaskResults, UploadReceipt


CONTRACT_VERSION = "frontend-api-v0.2.3-workbench-1"


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
        for status in (401, 403, 404, 409, 422, 429, 503):
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
        # 新版FastAPI可延迟展开include_router；最终Schema兜底不依赖内部路由对象形态。
        from .document_delete import DocumentDeletionError
        error_model = DocumentDeletionError.model_json_schema(ref_template="#/components/schemas/{model}")
        models = schema["components"]["schemas"]
        models.update(error_model.pop("$defs", {}))
        models["DocumentDeletionError"] = error_model
        for path, operations in schema.get("paths", {}).items():
            if not path.startswith("/api/"):
                continue
            for method, operation in operations.items():
                if method not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                    continue
                responses = operation.setdefault("responses", {})
                for status in (401, 403, 404, 409, 422, 429, 503):
                    default = {"description": "认证、权限、门禁、限流或服务不可用",
                               "content": {"application/json": {"schema": {
                                   "$ref": "#/components/schemas/DocumentDeletionError"}}}}
                    responses.setdefault(str(status), default)
                    content = responses[str(status)].get("content", {}).get("application/json", {})
                    if status == 422 and content.get("schema", {}).get("$ref") == "#/components/schemas/HTTPValidationError":
                        # 全局校验异常处理器返回机器错误包络，不使用框架默认detail数组。
                        responses[str(status)] = default
        for route in app.routes:
            dependant=getattr(route,'dependant',None)
            dependencies=getattr(dependant,'dependencies',())
            if not any(getattr(item.call,'__name__','')=='owner' for item in dependencies):
                continue
            for method in getattr(route,'methods',()):
                operation=schema.get('paths',{}).get(route.path,{}).get(method.lower())
                if operation is None:
                    continue
                parameters=operation.setdefault('parameters',[])
                if not any(item.get('name')=='owner_id' and item.get('in')=='query' for item in parameters):
                    parameters.append({'name':'owner_id','in':'query','required':False,
                        'schema':{'type':'string','minLength':1,'maxLength':128,'pattern':r'^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$'},
                        'description':'仅ADMIN可显式选择业务owner；其他角色传入返回403。管理员查询默认全局，上传和创建任务默认个人owner。'})
        schema["info"]["version"] = "0.2.3"
        schema["info"]["x-contract-version"] = CONTRACT_VERSION
        return schema
    app.openapi = openapi
