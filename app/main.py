import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import conversations_router, documents_router, users_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logger import setup_logger
from app.db.base import Base
from app.db.session import engine
from app.db.sqlite_migrations import migrate_sqlite_schema
from app.vector_store.faiss_index import FaissIndexManager


settings = get_settings()
setup_logger()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="BOT GPT backend APIs for open chat, RAG chat, and document ingestion.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "users", "description": "User lifecycle endpoints for UI and conversation ownership."},
        {"name": "conversations", "description": "Conversation lifecycle and chat message endpoints."},
        {"name": "documents", "description": "Document upload, chunking, and vector indexing endpoints."},
    ],
)


@app.on_event("startup")
def on_startup() -> None:
    if settings.hf_token and not os.getenv("HF_TOKEN"):
        os.environ["HF_TOKEN"] = settings.hf_token

    Base.metadata.create_all(bind=engine)
    migrate_sqlite_schema(engine)
    manager = FaissIndexManager(
        settings.vector_index_path,
        settings.vector_dim,
        mistral_api_key=settings.mistral_api_key,
        mistral_base_url=settings.mistral_base_url,
        mistral_embedding_model=settings.mistral_embedding_model,
    )
    manager.initialize()


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(exc),
            }
        },
    )


app.include_router(conversations_router)
app.include_router(documents_router)
app.include_router(users_router)
