import argparse
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

from app.db.database import SessionLocal
from app.models.transcript import Transcript, TranscriptChunk


DEFAULT_SOURCE_DIR = (
    Path(__file__).resolve().parents[2]
    / "lenny-transcripts-source"
    / "episodes"
)
TRANSCRIPT_SOURCE_ENV = "TRANSCRIPT_SOURCE_DIR"
CHUNK_SIZE = 4000
CHUNK_OVERLAP = 500


@dataclass
class IngestionCounts:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    created_chunks: int = 0
    updated_chunks: int = 0


def resolve_source_dir(source_dir: str | Path | None = None) -> Path:
    configured = source_dir or os.getenv(TRANSCRIPT_SOURCE_ENV)
    root = Path(configured).expanduser() if configured else DEFAULT_SOURCE_DIR
    if (root / "episodes").is_dir():
        root = root / "episodes"
    return root.resolve()


def split_into_chunks(text: str) -> list[str]:
    """Split transcript text into overlapping chunks."""
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def parse_transcript(file_path: Path):
    """Read YAML frontmatter and Markdown transcript content."""
    raw = file_path.read_text(encoding="utf-8", errors="replace")
    if not raw.startswith("---"):
        raise ValueError("Missing YAML frontmatter")

    parts = raw.split("---", 2)
    if len(parts) != 3:
        raise ValueError("Invalid frontmatter format")

    metadata = yaml.safe_load(parts[1]) or {}
    if not isinstance(metadata, dict):
        raise ValueError("Frontmatter must be a YAML mapping")

    return metadata, parts[2].strip()


def parse_publish_date(value):
    """Convert YAML date values into a Python datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return datetime.strptime(str(value), "%Y-%m-%d")


def portable_source_path(file_path: Path, source_dir: Path) -> str:
    return file_path.relative_to(source_dir).as_posix()


def _normalise_stored_path(value: str | None) -> str:
    return (value or "").replace("\\", "/").strip("/")


def _find_existing(db, portable_path: str):
    """Find both current portable rows and legacy absolute-path rows."""
    for transcript in db.query(Transcript).all():
        stored_path = _normalise_stored_path(transcript.source_path)
        if stored_path == portable_path or stored_path.endswith(
            f"/{portable_path}"
        ):
            return transcript
    return None


def _keywords_text(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(keyword) for keyword in value)
    return str(value or "")


def _metadata_values(metadata, content, portable_path):
    title = metadata.get("title")
    if not title:
        raise ValueError("Missing title metadata")
    if not content:
        raise ValueError("Missing transcript content")

    return {
        "episode_title": str(title),
        "guest_name": metadata.get("guest"),
        "source_url": metadata.get("source_url") or metadata.get("youtube_url"),
        "publish_date": parse_publish_date(metadata.get("publish_date")),
        "description": metadata.get("description"),
        "keywords": _keywords_text(metadata.get("keywords", [])),
        "content": content,
        "source_path": portable_path,
    }


def _load_existing_chunks(db, transcript):
    return db.query(TranscriptChunk).filter(
        TranscriptChunk.transcript_id == transcript.id
    ).order_by(TranscriptChunk.chunk_index).all()


def _replace_chunks(db, transcript, chunks):
    db.query(TranscriptChunk).filter(
        TranscriptChunk.transcript_id == transcript.id
    ).delete(synchronize_session=False)
    for chunk_index, chunk_content in enumerate(chunks):
        db.add(
            TranscriptChunk(
                transcript_id=transcript.id,
                chunk_index=chunk_index,
                content=chunk_content,
            )
        )


def ingest(source_dir: str | Path | None = None, db=None) -> IngestionCounts:
    root = resolve_source_dir(source_dir)
    if not root.exists():
        raise FileNotFoundError(f"Transcript directory not found: {root}")

    transcript_files = sorted(root.glob("*/transcript.md"))
    counts = IngestionCounts()
    database = db or SessionLocal()
    owns_database = db is None

    try:
        print(f"Source directory: {root}")
        print(f"Found {len(transcript_files)} transcript files.")

        for file_path in transcript_files:
            portable_path = portable_source_path(file_path, root)
            try:
                metadata, content = parse_transcript(file_path)
                values = _metadata_values(metadata, content, portable_path)
                chunks = split_into_chunks(content)
                existing = _find_existing(database, portable_path)

                if existing is None:
                    transcript = Transcript(**values)
                    database.add(transcript)
                    database.flush()
                    _replace_chunks(database, transcript, chunks)
                    counts.created += 1
                    counts.created_chunks += len(chunks)
                else:
                    existing_chunks = _load_existing_chunks(database, existing)
                    existing_chunk_values = [
                        chunk.content for chunk in existing_chunks
                    ]
                    changed = any(
                        getattr(existing, field) != value
                        for field, value in values.items()
                    ) or existing_chunk_values != chunks

                    if not changed:
                        counts.skipped += 1
                        continue

                    for field, value in values.items():
                        setattr(existing, field, value)
                    _replace_chunks(database, existing, chunks)
                    counts.updated += 1
                    counts.updated_chunks += len(chunks)

                database.commit()
            except Exception as exc:
                database.rollback()
                counts.errors += 1
                print(f"[SKIP] {portable_path}: {exc}")

        print()
        print("Ingestion complete.")
        print(f"Transcripts created: {counts.created}")
        print(f"Transcripts updated: {counts.updated}")
        print(f"Transcripts skipped: {counts.skipped}")
        print(f"Files with errors: {counts.errors}")
        print(f"Chunks created: {counts.created_chunks}")
        print(f"Chunks refreshed: {counts.updated_chunks}")
        return counts
    finally:
        if owns_database:
            database.close()


def main():
    parser = argparse.ArgumentParser(description="Ingest local Lenny transcripts")
    parser.add_argument(
        "--source-dir",
        default=None,
        help=(
            "Transcript checkout or episodes directory. Defaults to "
            f"${TRANSCRIPT_SOURCE_ENV} or the local sibling checkout."
        ),
    )
    args = parser.parse_args()
    ingest(args.source_dir)


if __name__ == "__main__":
    main()
