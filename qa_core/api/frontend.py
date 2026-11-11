"""按模块注册接口，复用调用方认证和现有任务服务。"""
from fastapi import Depends
from .common import FrontendReader


def register_frontend(app, service, config, owner, reader=None):
    reader = reader or FrontendReader(service, config)
    @app.get("/api/openapi.json", include_in_schema=False)
    def openapi(identity=Depends(owner)):
        return app.openapi()
    from .documents import register_documents
    register_documents(app, service, config, owner, reader)
    from .tasks import register_tasks
    register_tasks(app, service, config, owner, reader)
    from .review import register_review
    register_review(app, service, config, owner, reader)
    from .knowledge import register_knowledge
    register_knowledge(app, service, config, owner, reader)
    from .search import register_search
    register_search(app, service, config, owner, reader)
    from .monitoring import register_monitoring
    register_monitoring(app, service, config, owner, reader)
    app.state.frontend_reader = reader
