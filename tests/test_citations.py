import os
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:123@localhost:5432/lenny_growth",
)

from app.services.agent import AgentResponse
from app.services.artifacts import ArtifactRequest, build_artifact_result
from app.services.citations import map_source_references
from app.services.chat import chat_with_transcripts


RETRIEVED = [
    {
        "episode_title": "Activation and retention",
        "guest_name": "Elena Verna",
        "source_url": "https://example.com/elena",
        "transcript_id": "transcript-elena",
        "chunk_id": "chunk-elena",
        "content": "Elena transcript evidence.",
    },
    {
        "episode_title": "Growth loops",
        "guest_name": "Casey Winters",
        "source_url": "https://example.com/casey",
        "transcript_id": "transcript-casey",
        "chunk_id": "chunk-casey",
        "content": "Casey transcript evidence.",
    },
]


class CitationIntegrityTest(unittest.TestCase):
    def test_references_map_only_to_authoritative_retrieved_sources(self):
        sources = map_source_references(
            "Kevin Yien explains this approach. SOURCE 2. SOURCE 1. SOURCE 5. SOURCE 1.",
            RETRIEVED,
        )

        self.assertEqual(
            sources,
            [
                {
                    "episode_title": "Growth loops",
                    "guest_name": "Casey Winters",
                    "source_url": "https://example.com/casey",
                },
                {
                    "episode_title": "Activation and retention",
                    "guest_name": "Elena Verna",
                    "source_url": "https://example.com/elena",
                },
            ],
        )
        self.assertNotIn("Kevin Yien", str(sources))
        self.assertNotIn("transcript_id", sources[0])
        self.assertNotIn("chunk_id", sources[0])

    def test_chat_response_sources_are_mapped_from_retrieval(self):
        session_query = MagicMock()
        session_query.filter.return_value.first.return_value = object()
        messages_query = MagicMock()
        messages_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db = MagicMock()
        db.query.side_effect = [session_query, messages_query]

        with patch(
            "app.services.chat.generate_grounded_answer",
            return_value=AgentResponse(
                answer="Kevin Yien explains this approach. SOURCE 2 SOURCE 5 SOURCE 2",
                results=RETRIEVED,
            ),
        ):
            response = chat_with_transcripts(
                db=db,
                session_id=uuid4(),
                query="How should we improve growth?",
                limit=5,
            )

        self.assertEqual(len(response["sources"]), 1)
        self.assertEqual(response["sources"][0]["guest_name"], "Casey Winters")
        self.assertNotIn("Kevin Yien", str(response["sources"]))

    def test_missing_valid_citation_is_acknowledged_without_inventing_sources(self):
        session_query = MagicMock()
        session_query.filter.return_value.first.return_value = object()
        messages_query = MagicMock()
        messages_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db = MagicMock()
        db.query.side_effect = [session_query, messages_query]

        with patch(
            "app.services.chat.generate_grounded_answer",
            return_value=AgentResponse(
                answer="Kevin Yien explains this approach. SOURCE 5",
                results=RETRIEVED,
            ),
        ):
            response = chat_with_transcripts(
                db=db,
                session_id=uuid4(),
                query="How should we improve growth?",
                limit=5,
            )

        self.assertEqual(response["sources"], [])
        self.assertIn("transcript source citation", response["answer"])

    def test_artifact_sources_use_the_same_authoritative_mapping(self):
        artifact = build_artifact_result(
            ArtifactRequest(artifact_type="markdown", title="Growth plan"),
            "# Plan\n\nARTIFACT_SOURCES: SOURCE 2, SOURCE 5, SOURCE 2",
            RETRIEVED,
        )

        self.assertEqual(len(artifact.sources), 1)
        self.assertEqual(artifact.sources[0]["guest_name"], "Casey Winters")


if __name__ == "__main__":
    unittest.main()
