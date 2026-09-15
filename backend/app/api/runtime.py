import os

from fastapi import APIRouter


router = APIRouter(prefix="/runtime", tags=["Runtime"])


@router.get("")
def get_runtime_info():
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    model = (
        os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        if provider == "ollama"
        else os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )
    return {"provider": provider, "model": model}