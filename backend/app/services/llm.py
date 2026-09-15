import os
import logging

from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMConfigurationError(RuntimeError):
    """Raised when the selected model provider is not configured."""


class LLMServiceError(RuntimeError):
    """Raised when a configured model provider cannot answer."""


def _provider_and_model() -> tuple[str, str]:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "ollama":
        return provider, os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    if provider == "openai":
        return provider, os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    raise LLMConfigurationError("Unsupported LLM provider configuration.")


def _timeout_seconds() -> float:
    value = os.getenv("LLM_TIMEOUT_SECONDS", "180")
    try:
        return max(float(value), 30.0)
    except ValueError:
        return 180.0


def _ollama_num_ctx() -> int:
    value = os.getenv("OLLAMA_NUM_CTX", "4096")
    try:
        return max(int(value), 1)
    except ValueError:
        return 4096


def get_llm_client() -> OpenAI:
    provider, _ = _provider_and_model()

    if provider == "ollama":
        return OpenAI(
            base_url=os.getenv(
                "OLLAMA_BASE_URL",
                "http://localhost:11434/v1",
            ),
            api_key="ollama",
            timeout=_timeout_seconds(),
        )

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise LLMConfigurationError("OpenAI credentials are not configured.")

        return OpenAI(api_key=api_key, timeout=_timeout_seconds())

    raise LLMConfigurationError("Unsupported LLM provider configuration.")


def generate_answer(
    system_prompt: str,
    user_prompt: str,
) -> str:
    provider, model = _provider_and_model()
    logger.info(
        "LLM request started",
        extra={
            "event": "llm_request_start",
            "provider": provider,
            "model": model,
            "operation": "chat_completion",
        },
    )

    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            **(
                {"extra_body": {"options": {"num_ctx": _ollama_num_ctx()}}}
                if provider == "ollama"
                else {}
            ),
        )
        answer = response.choices[0].message.content or ""
        if not answer:
            raise LLMServiceError("Model returned an empty response.")
        return answer
    except LLMConfigurationError:
        logger.error(
            "LLM configuration failed",
            extra={
                "event": "llm_configuration_failure",
                "provider": provider,
                "model": model,
                "operation": "chat_completion",
                "error_type": "configuration",
            },
        )
        raise
    except Exception as error:
        logger.error(
            "LLM request failed",
            extra={
                "event": "llm_request_failure",
                "provider": provider,
                "model": model,
                "operation": "chat_completion",
                "error_type": type(error).__name__,
            },
        )
        raise LLMServiceError("The model provider is unavailable.") from error