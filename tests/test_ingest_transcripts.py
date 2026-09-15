import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from unittest.mock import patch

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:123@localhost:5432/lenny_growth",
)
sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from app.models.transcript import Transcript, TranscriptChunk
from scripts.ingest_transcripts import (
    ingest,
    portable_source_path,
    resolve_source_dir,
)


class InMemoryQuery:
    def __init__(self, database, model):
        self.database = database
        self.model = model
        self.rows = database.rows_for(model)

    def filter(self, condition):
        value = condition.right.value
        if self.model is TranscriptChunk:
            self.rows = [
                row for row in self.rows
                if row.transcript_id == value
            ]
        return self

    def order_by(self, _ordering):
        self.rows.sort(key=lambda row: row.chunk_index)
        return self

    def all(self):
        return list(self.rows)

    def delete(self, synchronize_session=False):
        del self.database.chunks[:]


class InMemoryDatabase:
    def __init__(self):
        self.transcripts = []
        self.chunks = []

    def rows_for(self, model):
        return self.transcripts if model is Transcript else self.chunks

    def query(self, model):
        return InMemoryQuery(self, model)

    def add(self, item):
        if isinstance(item, Transcript):
            self.transcripts.append(item)
        else:
            self.chunks.append(item)

    def flush(self):
        for transcript in self.transcripts:
            if transcript.id is None:
                transcript.id = uuid4()

    def commit(self):
        pass

    def rollback(self):
        pass


class IngestionTest(unittest.TestCase):
    def write_transcript(self, root, episode, body, metadata=None):
        episode_dir = Path(root) / "episodes" / episode
        episode_dir.mkdir(parents=True, exist_ok=True)
        metadata = metadata or {
            "guest": "Guest Name",
            "title": "Episode title",
            "youtube_url": "https://example.com/video",
            "publish_date": "2024-01-02",
            "description": "Description",
            "keywords": ["growth", "activation"],
        }
        lines = ["---"]
        for key, value in metadata.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                lines.extend(f"- {item}" for item in value)
            else:
                lines.append(f"{key}: {value}")
        lines.extend(["---", body])
        (episode_dir / "transcript.md").write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

    def test_source_directory_configuration_and_portable_path(self):
        with TemporaryDirectory() as temp_dir:
            checkout = Path(temp_dir) / "checkout"
            episodes = checkout / "episodes"
            file_path = episodes / "episode-name" / "transcript.md"
            file_path.parent.mkdir(parents=True)
            file_path.write_text("content", encoding="utf-8")

            self.assertEqual(resolve_source_dir(checkout), episodes.resolve())
            with patch.dict(os.environ, {"TRANSCRIPT_SOURCE_DIR": str(checkout)}):
                self.assertEqual(resolve_source_dir(), episodes.resolve())
            self.assertEqual(
                portable_source_path(file_path, episodes),
                "episode-name/transcript.md",
            )

    def test_ingestion_is_idempotent_and_refreshes_existing_records(self):
        with TemporaryDirectory() as temp_dir:
            self.write_transcript(temp_dir, "episode-name", "original content")
            database = InMemoryDatabase()

            first = ingest(temp_dir, db=database)
            second = ingest(temp_dir, db=database)

            self.assertEqual(first.created, 1)
            self.assertEqual(second.skipped, 1)
            self.assertEqual(len(database.transcripts), 1)
            self.assertEqual(len(database.chunks), 1)
            self.assertEqual(database.transcripts[0].source_path, "episode-name/transcript.md")

            self.write_transcript(temp_dir, "episode-name", "updated content")
            refreshed = ingest(temp_dir, db=database)

            self.assertEqual(refreshed.updated, 1)
            self.assertEqual(len(database.transcripts), 1)
            self.assertEqual(database.transcripts[0].content, "updated content")
            self.assertEqual(database.chunks[0].content, "updated content")

    def test_legacy_absolute_path_is_recognized_and_normalized(self):
        with TemporaryDirectory() as temp_dir:
            self.write_transcript(temp_dir, "episode-name", "content")
            database = InMemoryDatabase()
            ingest(temp_dir, db=database)
            database.transcripts[0].source_path = (
                "C:\\Users\\someone\\lenny-transcripts-source\\"
                "episode-name\\transcript.md"
            )

            result = ingest(temp_dir, db=database)

            self.assertEqual(result.updated, 1)
            self.assertEqual(len(database.transcripts), 1)
            self.assertEqual(database.transcripts[0].source_path, "episode-name/transcript.md")

    def test_malformed_files_are_reported_and_do_not_stop_ingestion(self):
        with TemporaryDirectory() as temp_dir:
            self.write_transcript(temp_dir, "valid", "valid content")
            invalid_dir = Path(temp_dir) / "episodes" / "invalid"
            invalid_dir.mkdir(parents=True)
            (invalid_dir / "transcript.md").write_text(
                "not yaml frontmatter",
                encoding="utf-8",
            )
            database = InMemoryDatabase()

            result = ingest(temp_dir, db=database)

            self.assertEqual(result.created, 1)
            self.assertEqual(result.errors, 1)
            self.assertEqual(len(database.transcripts), 1)


if __name__ == "__main__":
    unittest.main()
