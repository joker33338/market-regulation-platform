"""按模块注册接口，复用调用方认证和现有任务服务。"""
from fastapi import Depends
from .common import FrontendReader


def register_frontend(app, service, config, owner, reader=None, principal=None):
    principal = principal or owner
    reader = reader or FrontendReader(service, config)
    from qa_core.storage.mysql_review_ledger import MySQLReviewLedger
    app.state.review_ledger = MySQLReviewLedger.from_env()
    @app.get("/api/openapi.json", include_in_schema=False)
    def openapi(identity=Depends(principal)):
        return app.openapi()
    from .documents import register_documents
    register_documents(app, service, config, owner, reader, principal)
    from .document_delete import register_document_delete
    register_document_delete(app, principal, reader)
    from .tasks import register_tasks
    register_tasks(app, service, config, owner, reader)
    from .review import register_review
    register_review(app, service, config, principal, reader)
    from .review_writes import register_review_writes
    register_review_writes(app, principal, reader)
    from .knowledge import register_knowledge
    register_knowledge(app, service, config, owner, reader, principal)
    from .search import register_search
    register_search(app, service, config, principal, reader)
    from .monitoring import register_monitoring
    register_monitoring(app, service, config, owner, reader, principal)
    from .resources import register_resources
    register_resources(app, principal)
    from .operational_logs import register_operational_logs
    register_operational_logs(app, config, principal)
    from .ingestion import register_ingestion
    register_ingestion(app, principal, reader, config)
    from .capabilities import register_capabilities
    register_capabilities(app, principal)
    from .contracts import annotate_legacy
    from .business_library import register_business_library
    register_business_library(app, principal, reader)
    annotate_legacy(app)
    app.state.frontend_reader = reader
    reader.known_owner_ids=lambda:[identity.owner_id for identity in app.state.auth_registry.principals() if identity.owner_id]
