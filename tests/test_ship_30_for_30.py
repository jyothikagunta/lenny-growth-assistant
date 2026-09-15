import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:123@localhost:5432/lenny_growth",
)

from app.services import agent
from app.services.skills.ship_30_for_30 import (
    SHIP_30_FOR_30_PRINCIPLES,
    SHIP_30_FOR_30_SOURCE_URLS,
    SHIP_30_FOR_30_TOOL_NAME,
    build_ship_30_for_30_instructions,
    build_ship_30_for_30_prompt,
)


class Ship30For30SkillTest(unittest.TestCase):
    def test_principles_are_encoded(self):
        for principle in (
            "Specificity",
            "Strong headline and hook",
            "Clear writing direction",
            "Consistent structure",
            "Stories, examples, and advice",
            "Writing rhythm",
            "Differentiation",
            "Lean Writing",
            "Useful reader outcome",
            "Skimmability",
        ):
            self.assertIn(principle, SHIP_30_FOR_30_PRINCIPLES)

    def test_output_and_grounding_requirements_are_explicit(self):
        instructions = build_ship_30_for_30_instructions("write about growth")
        prompt = build_ship_30_for_30_prompt(
            history="No previous conversation history.",
            query="Ship 30 for 30: write about growth",
            context="SOURCE 1\nTranscript excerpt",
        )

        self.assertIn("approximately 1,250 words", instructions)
        self.assertIn("strong hook", instructions)
        self.assertIn("Sources section", instructions)
        self.assertIn("only factual source", instructions)
        self.assertIn("Lenny transcript context", prompt)
        self.assertIn("SOURCE 1", prompt)
        self.assertIn(SHIP_30_FOR_30_SOURCE_URLS[0], instructions)
        self.assertIn(SHIP_30_FOR_30_SOURCE_URLS[1], instructions)

    def test_local_agent_routes_ship_request_to_skill_prompt(self):
        retrieved = [
            {
                "episode_title": "Episode",
                "guest_name": "Guest",
                "source_url": "url",
                "content": "Transcript evidence",
            }
        ]

        with patch.dict(os.environ, {"AGENT_BACKEND": "local"}), patch(
            "app.services.agent.search_transcripts",
            return_value=retrieved,
        ), patch(
            "app.services.agent.generate_answer",
            return_value="Draft\n\nSources:\n- SOURCE 1",
        ) as generate:
            response = agent.generate_grounded_answer(
                db=MagicMock(),
                query="Ship 30 for 30: write a growth essay",
                history="No previous conversation history.",
                limit=3,
            )

        prompt = generate.call_args.kwargs["user_prompt"]
        self.assertEqual(response.results, retrieved)
        self.assertIn("Specificity", prompt)
        self.assertIn("approximately 1,250 words", prompt)
        self.assertIn("SOURCE 1", prompt)
        self.assertIn("only evidence for Lenny-related facts", prompt)

    def test_skill_is_a_restricted_capability_not_a_builtin_tool(self):
        class FakeOptions:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        options = agent._build_claude_options(
            FakeOptions,
            object(),
            skill_enabled=True,
        )

        self.assertEqual(options.tools, [])
        self.assertIn(
            "mcp__lenny_transcripts__" + SHIP_30_FOR_30_TOOL_NAME,
            options.allowed_tools,
        )
        self.assertIn("Bash", options.disallowed_tools)
        self.assertTrue(options.strict_mcp_config)


if __name__ == "__main__":
    unittest.main()