import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.utils.logging import setup_logging

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):

    settings = get_settings()
    setup_logging()

    logger.info(
        "api_server_starting",
        env=settings.app_env,
        mock_llm=settings.mock_llm,
        mock_github=settings.mock_github
    )


    try:
        _ = settings.github_private_key
        logger.info("github_private_key_loaded")
    except FileNotFoundError as e:
        logger.error("github_private_key_missing", error=str(e))
        raise

    yield

    from app.utils.queue import close_queue
    await close_queue()

    logger.info("api_server_stopping")

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="GitHub Review Agent",
        description="Multi-tenant GitHub App for AI-powered code reviews",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url= None
    )


    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"]
    )

    from app.routes.health import router as health_router
    app.include_router(health_router)

    from app.routes.webhooks import router as webhook_router
    app.include_router(webhook_router, prefix="/webhooks")

    return app

app = create_app()

    