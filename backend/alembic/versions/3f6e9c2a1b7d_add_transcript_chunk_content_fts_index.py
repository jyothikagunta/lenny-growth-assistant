"""add transcript chunk content full-text search index

Revision ID: 3f6e9c2a1b7d
Revises: 1852815ba4ef
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3f6e9c2a1b7d"
down_revision: Union[str, Sequence[str], None] = "1852815ba4ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "ix_transcript_chunks_content_fts"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE INDEX {INDEX_NAME}
        ON transcript_chunks
        USING gin (to_tsvector('english', content))
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
