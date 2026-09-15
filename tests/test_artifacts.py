import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:123@localhost:5432/lenny_growth",
)

from app.services import agent
from app.services.artifacts import (
    ArtifactRequest,
    HYPOTHETICAL_CLAIM_LABEL,
    build_artifact_result,
    detect_artifact_request,
)


RETRIEVED = [
    {
        "episode_title": "Growth episode",
        "guest_name": "Guest",
        "source_url": "https://example.com/episode",
        "content": "Transcript evidence about activation and retention.",
    }
]


class ArtifactGenerationTest(unittest.TestCase):
    def test_normal_chat_does_not_become_an_artifact(self):
        with patch.dict(os.environ, {"AGENT_BACKEND": "local"}), patch(
            "app.services.agent.search_transcripts",
            return_value=RETRIEVED,
        ), patch(
            "app.services.agent.generate_answer",
            return_value="Answer\nSources:\n- SOURCE 1",
        ) as generate:
            response = agent.generate_grounded_answer(
                db=MagicMock(),
                query="How should we improve activation?",
                history="",
                limit=3,
            )

        self.assertIsNone(response.artifact)
        self.assertEqual(generate.call_count, 1)

    def test_explicit_markdown_artifact_request_is_detected(self):
        request = detect_artifact_request("Generate a Markdown artifact about activation")

        self.assertIsNotNone(request)
        self.assertEqual(request.artifact_type, "markdown")

    def test_explicit_html_artifact_request_is_detected(self):
        request = detect_artifact_request("Create an HTML landing page for activation")

        self.assertIsNotNone(request)
        self.assertEqual(request.artifact_type, "html")

    def test_artifact_has_structured_fields_and_retrieval_context(self):
        generated = "# Activation plan\n\nUse the evidence.\n\nARTIFACT_SOURCES: SOURCE 1"
        with patch.dict(os.environ, {"AGENT_BACKEND": "local"}), patch(
            "app.services.agent.search_transcripts",
            return_value=RETRIEVED,
        ), patch(
            "app.services.agent.generate_answer",
            return_value=generated,
        ) as generate:
            response = agent.generate_grounded_answer(
                db=MagicMock(),
                query="Create a product strategy document for activation",
                history="",
                limit=3,
            )

        self.assertEqual(response.artifact.artifact_type, "markdown")
        self.assertEqual(response.artifact.content, "# Activation plan\n\nUse the evidence.")
        self.assertEqual(response.artifact.sources[0]["episode_title"], "Growth episode")
        self.assertIn("Transcript evidence about activation", generate.call_args.kwargs["user_prompt"])

    def test_html_is_untrusted_and_is_never_executed(self):
        generated = (
            "<!doctype html><html><style>body { color: red; }</style>"
            "<body>Activation</body></html>\nARTIFACT_SOURCES: NONE"
        )
        with patch.dict(os.environ, {"AGENT_BACKEND": "local"}), patch(
            "app.services.agent.search_transcripts",
            return_value=RETRIEVED,
        ), patch(
            "app.services.agent.generate_answer",
            return_value=generated,
        ), patch("os.system") as system:
            response = agent.generate_grounded_answer(
                db=MagicMock(),
                query="Create an HTML landing page for activation",
                history="",
                limit=3,
            )

        self.assertEqual(response.artifact.artifact_type, "html")
        self.assertTrue(response.artifact.is_untrusted)
        self.assertIn("<!doctype html>", response.artifact.content)
        system.assert_not_called()

    def test_artifact_prompt_forbids_invented_metrics_and_guests(self):
        generated = "# Plan\n\nUse the evidence.\n\nARTIFACT_SOURCES: SOURCE 1"
        with patch.dict(os.environ, {"AGENT_BACKEND": "local"}), patch(
            "app.services.agent.search_transcripts",
            return_value=RETRIEVED,
        ), patch(
            "app.services.agent.generate_answer",
            return_value=generated,
        ) as generate:
            agent.generate_grounded_answer(
                db=MagicMock(),
                query="Create a Markdown artifact about activation",
                history="",
                limit=3,
            )

        prompt = generate.call_args.kwargs["user_prompt"]
        self.assertIn("Never invent percentages", prompt)
        self.assertIn("hypothetical", prompt)
        self.assertIn("Guest identity", prompt)

    def test_unsupported_metrics_and_guest_are_not_presented_as_facts(self):
        retrieved = [
            {
                "episode_title": "Doing the small stuff",
                "guest_name": "Elena Verna",
                "source_url": "https://example.com/elena",
                "content": (
                    "Focus on the small stuff and stay consistent. "
                    "Qualitative advice about product growth, with no metrics."
                ),
            }
        ]
        generated = """
# The small stuff

Casey Winters said the small stuff is what compounds.

- Increased sales by 25%
- Improved user retention by 30%
- Increased social media engagement by 50%

ARTIFACT_SOURCES: SOURCE 1
"""
        artifact = build_artifact_result(
            ArtifactRequest(artifact_type="markdown", title="Small stuff"),
            generated,
            retrieved,
        )

        self.assertNotIn("Casey Winters", artifact.content)
        self.assertEqual(artifact.sources[0]["guest_name"], "Elena Verna")
        self.assertIn("a guest from the retrieved transcript excerpts", artifact.content)
        for claim in (
            "Increased sales by 25%",
            "Improved user retention by 30%",
            "Increased social media engagement by 50%",
        ):
            self.assertIn(f"{HYPOTHETICAL_CLAIM_LABEL} {claim}", artifact.content)

    def test_supported_metrics_and_guest_remain_factual(self):
        retrieved = [
            {
                "episode_title": "Retention loops",
                "guest_name": "Elena Verna",
                "source_url": "https://example.com/elena",
                "content": "Elena Verna said retention improved 30% after the change.",
            }
        ]
        generated = (
            "Elena Verna said retention improved 30% after the change.\n\n"
            "ARTIFACT_SOURCES: SOURCE 1"
        )
        artifact = build_artifact_result(
            ArtifactRequest(artifact_type="markdown", title="Retention"),
            generated,
            retrieved,
        )

        self.assertIn("Elena Verna said retention improved 30%", artifact.content)
        self.assertNotIn("Hypothetical example", artifact.content)
        self.assertEqual(artifact.sources[0]["guest_name"], "Elena Verna")


if __name__ == "__main__":
    unittest.main()