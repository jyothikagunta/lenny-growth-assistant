from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import configure_logging
from app.api.sessions import router as sessions_router
from app.api.messages import router as messages_router
from app.api.search import router as search_router
from app.api.chat import router as chat_router
from app.api.runtime import router as runtime_router

configure_logging()

app = FastAPI(
    title="Lenny Growth Assistant",
    description=(
        "AI-powered product and growth assistant "
        "grounded in Lenny's Podcast transcripts."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


app.include_router(
    sessions_router,
    prefix="/api/v1",
)

app.include_router(
    messages_router,
    prefix="/api/v1",
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "lenny-growth-assistant",
    }


@app.get("/")
def root():
    return {
        "message": "Lenny Growth Assistant API",
    }
app.include_router(
    search_router,
    prefix="/api/v1",
)
app.include_router(chat_router, prefix="/api/v1")
app.include_router(runtime_router, prefix="/api/v1")