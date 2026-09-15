import os
import unittest
import builtins
from unittest.mock import MagicMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:123@localhost:5432/lenny_growth",
)

from app.services import agent
from app.services.agent import AgentResponse, AgentConfigurationError
from app.services.chat import chat_with_transcripts


class AgentFacadeTest(unittest.TestCase):
    def test_local_backend_uses_existing_llm_path(self):
        result = {
            "episode_title": "Episode",
            "guest_name": "Guest",
            "source_url": "url",
            "content": "Transcript evidence",
        }

        with patch.dict(os.environ, {"AGENT_BACKEND": "local"}), patch(
            "app.services.agent.search_transcripts",
            return_value=[result],
        ) as search, patch(
            "app.services.agent.generate_answer",
            return_value="Answer\nSources:\n- SOURCE 1",
        ) as generate:
            response = agent.generate_grounded_answer(
                db=MagicMock(),
                query="question",
                history="USER: previous",
                limit=3,
            )

        search.assert_called_once()
        generate.assert_called_once()
        self.assertEqual(response.answer, "Answer\nSources:\n- SOURCE 1")
        self.assertEqual(response.results, [result])
        self.assertIn(
            "evidence for factual claims",
            generate.call_args.kwargs["system_prompt"],
        )

    def test_claude_backend_is_selected(self):
        expected = AgentResponse(answer="Claude answer", results=[])
        with patch.dict(os.environ, {"AGENT_BACKEND": "claude"}), patch(
            "app.services.agent._generate_claude_answer",
            return_value=expected,
        ) as generate:
            response = agent.generate_grounded_answer(
                db=MagicMock(),
                query="question",
                history="",
                limit=1,
            )

        generate.assert_called_once()
        self.assertIs(response, expected)

    def test_claude_backend_requires_credentials(self):
        with patch.dict(
            os.environ,
            {"AGENT_BACKEND": "claude"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                AgentConfigurationError,
                "ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN",
            ):
                agent.generate_grounded_answer(
                    db=MagicMock(),
                    query="question",
                    history="",
                    limit=1,
                )

    def test_claude_backend_reports_missing_sdk(self):
        real_import = builtins.__import__

        def import_without_sdk(name, *args, **kwargs):
            if name == "claude_agent_sdk":
                raise ImportError("SDK unavailable for test")
            return real_import(name, *args, **kwargs)

        with patch.dict(
            os.environ,
            {
                "AGENT_BACKEND": "claude",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=True,
        ), patch("builtins.__import__", side_effect=import_without_sdk):
            with self.assertRaisesRegex(
                AgentConfigurationError,
                "requires the claude-agent-sdk package",
            ):
                agent.generate_grounded_answer(
                    db=MagicMock(),
                    query="question",
                    history="",
                    limit=1,
                )

    def test_claude_options_disable_unrestricted_tools(self):
        class FakeOptions:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        options = agent._build_claude_options(FakeOptions, object())

        self.assertEqual(options.tools, [])
        self.assertEqual(options.allowed_tools, [agent.CLAUDE_ALLOWED_TOOL])
        self.assertIn("Bash", options.disallowed_tools)
        self.assertTrue(options.strict_mcp_config)

    def test_chat_service_calls_agent_facade(self):
        session_query = MagicMock()
        session_query.filter.return_value.first.return_value = object()
        messages_query = MagicMock()
        messages_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db = MagicMock()
        db.query.side_effect = [session_query, messages_query]

        with patch(
            "app.services.chat.generate_grounded_answer",
            return_value=AgentResponse(answer="answer", results=[]),
        ) as generate:
            response = chat_with_transcripts(
                db=db,
                session_id=uuid4(),
                query="question",
                limit=1,
            )

        generate.assert_called_once()
        self.assertEqual(response["answer"], "answer")


if __name__ == "__main__":
    unittest.main()