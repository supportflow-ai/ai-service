from __future__ import annotations

from fastapi import FastAPI

from supportflow_ai.api.errors import register_exception_handlers
from supportflow_ai.api.middleware import LimitRequestBodyMiddleware
from supportflow_ai.api.routes.classification import router as classification_router
from supportflow_ai.api.routes.health import router as health_router
from supportflow_ai.api.routes.knowledge import router as knowledge_router
from supportflow_ai.application.classification.service import ClassifyTicket
from supportflow_ai.application.embedding.index import PrepareKnowledgeIndex
from supportflow_ai.bootstrap import build_classifier, build_knowledge_index_preparer
from supportflow_ai.config import Settings, get_settings
from supportflow_ai.observability.logging import configure_logging


def create_app(
    settings: Settings | None = None, *, index_preparer: PrepareKnowledgeIndex | None = None,
) -> FastAPI:
    settings = settings if settings is not None else get_settings()
    configure_logging(settings.log_level)
    classifier = build_classifier(settings)
    is_production = settings.environment == "production"

    app = FastAPI(
        title="SupportFlow AI Service",
        version="0.1.1",
        docs_url=None if is_production else "/docs",
        openapi_url=None if is_production else "/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.classifier = classifier
    app.state.classify_ticket = ClassifyTicket(classifier)
    if index_preparer is None:
        index_preparer = build_knowledge_index_preparer(settings)
    app.state.prepare_knowledge_index = index_preparer
    app.add_middleware(LimitRequestBodyMiddleware, max_bytes=settings.max_request_bytes)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(classification_router)
    app.include_router(knowledge_router)
    return app


# Intentionally no eager `app = create_app()` import side effect.
# Run with: uvicorn supportflow_ai.main:create_app --factory
# This ensures security settings are validated when the server boots,
# while tests can explicitly construct an app with test-only settings.
