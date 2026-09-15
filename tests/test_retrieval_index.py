import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:123@localhost:5432/lenny_growth",
)

from app.services.retrieval import search_transcripts


class RetrievalIndexTest(unittest.TestCase):
    def test_fts_migration_defines_matching_gin_expression(self):
        migration = Path(__file__).parents[1] / "backend" / "alembic" / "versions" / "3f6e9c2a1b7d_add_transcript_chunk_content_fts_index.py"
        content = migration.read_text(encoding="utf-8")

        self.assertIn("ix_transcript_chunks_content_fts", content)
        self.assertIn("USING gin (to_tsvector('english', content))", content)
        self.assertIn('down_revision: Union[str, Sequence[str], None] = "1852815ba4ef"', content)

    def test_retrieval_preserves_english_search_and_rank_contract(self):
        db = MagicMock()
        db.execute.return_value.mappings.return_value.all.return_value = [
            {
                "episode_title": "Activation episode",
                "guest_name": "Elena Verna",
                "source_url": "https://example.com/activation",
                "content": "Activation transcript chunk",
            }
        ]

        results = search_transcripts(db=db, query="activation", limit=5)
        sql = str(db.execute.call_args.args[0])

        self.assertEqual(results[0]["episode_title"], "Activation episode")
        self.assertIn("to_tsvector('english', tc.content)", sql)
        self.assertIn("websearch_to_tsquery('english', :query)", sql)
        self.assertIn("ts_rank(", sql)
        self.assertIn("ORDER BY rank DESC", sql)
        self.assertIn("LIMIT :limit", sql)
        self.assertEqual(
            db.execute.call_args.args[1],
            {"query": "activation", "limit": 5},
        )


if __name__ == "__main__":
    unittest.main()
