import logging
import os
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:123@localhost:5432/lenny_growth",
)

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.services import agent
from app.services.agent import AgentConfigurationError, AgentResponse
from app.services.chat import chat_with_transcripts
from app.services.llm import (
    LLMConfigurationError,
    LLMServiceError,
    generate_answer,
    get_llm_client,
)
from app.services.retrieval import RetrievalServiceError, search_transcripts


RESULT = {
    "episode_title": "Episode",
    "guest_name": "Guest",
    "source_url": "https://example.com/episode",
    "content": "Transcript evidence",
}


class FailureHandlingTest(unittest.TestCase):
    def test_missing_openai_key_is_a_safe_configuration_error(self):
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "openai"},
            clear=True,
        ):
            with self.assertRaises(LLMConfigurationError):
                get_llm_client()

    def test_unsupported_provider_is_rejected_without_provider_details(self):
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "secret-provider"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                LLMConfigurationError,
                "Unsupported LLM provider configuration",
            ):
                generate_answer("system prompt with secret", "user prompt")

    def test_llm_failure_is_sanitized_and_logged_without_prompt_content(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError(
            "provider secret api-key=hidden"
        )
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}), patch(
            "app.services.llm.get_llm_client",
            return_value=client,
        ), self.assertLogs("app.services.llm", level=logging.ERROR) as logs:
            with self.assertRaises(LLMServiceError) as raised:
                generate_answer("full secret system prompt", "private user prompt")

        self.assertEqual(str(raised.exception), "The model provider is unavailable.")
        self.assertNotIn("private user prompt", " ".join(logs.output))
        self.assertNotIn("api-key", " ".join(logs.output))

    def test_retrieval_failure_is_separate_from_empty_retrieval(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("database password=hidden")
        with self.assertLogs("app.services.retrieval", level=logging.ERROR) as logs:
            with self.assertRaises(RetrievalServiceError):
                search_transcripts(db, "activation")
        self.assertNotIn("password", " ".join(logs.output))

        empty_db = MagicMock()
        empty_db.execute.return_value.mappings.return_value.all.return_value = []
        with self.assertLogs("app.services.retrieval", level=logging.INFO) as logs:
            self.assertEqual(search_transcripts(empty_db, "unknown"), [])
        self.assertEqual(logs.records[-1].event, "retrieval_empty")

    def test_chat_converts_agent_failures_to_safe_503(self):
        db = self._chat_db()
        with patch(
            "app.services.chat.generate_grounded_answer",
            side_effect=AgentConfigurationError("OPENAI_API_KEY=secret"),
        ):
            with self.assertRaises(HTTPException) as raised:
                chat_with_transcripts(db, uuid4(), "question")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertNotIn("secret", str(raised.exception.detail))

        db = self._chat_db()
        with patch(
            "app.services.chat.generate_grounded_answer",
            side_effect=RetrievalServiceError("database password=secret"),
        ):
            with self.assertRaises(HTTPException) as raised:
                chat_with_transcripts(db, uuid4(), "question")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertNotIn("password", str(raised.exception.detail))

    def test_database_persistence_failure_is_safe_503(self):
        db = self._chat_db()
        db.commit.side_effect = SQLAlchemyError("connection password=secret")

        with patch(
            "app.services.chat.generate_grounded_answer",
            return_value=AgentResponse(answer="answer", results=[]),
        ), self.assertRaises(HTTPException) as raised:
            chat_with_transcripts(db, uuid4(), "question")

        self.assertEqual(raised.exception.status_code, 503)
        self.assertNotIn("password", str(raised.exception.detail))
        db.rollback.assert_called_once()

    def test_artifact_failure_returns_safe_response_without_artifact(self):
        with patch.dict(os.environ, {"AGENT_BACKEND": "local"}), patch(
            "app.services.agent.search_transcripts",
            return_value=[RESULT],
        ), patch(
            "app.services.agent.generate_artifact",
            side_effect=RuntimeError("artifact path=/private/secret"),
        ):
            response = agent.generate_grounded_answer(
                db=MagicMock(),
                query="Create a Markdown artifact about activation",
                history="",
                limit=3,
            )

        self.assertIsNone(response.artifact)
        self.assertEqual(
            response.answer,
            "Artifact generation is temporarily unavailable. Please try again.",
        )

    def test_empty_context_prompt_requires_insufficient_support_statement(self):
        prompt = agent.build_user_prompt("", "question", "No relevant transcript material was found.")
        self.assertIn(
            "only when the retrieved context",
            prompt,
        )
        self.assertIn("contains no relevant evidence", prompt)

    @staticmethod
    def _chat_db():
        session_query = MagicMock()
        session_query.filter.return_value.first.return_value = object()
        messages_query = MagicMock()
        messages_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db = MagicMock()
        db.query.side_effect = [session_query, messages_query]
        return db


if __name__ == "__main__":
    unittest.main()
