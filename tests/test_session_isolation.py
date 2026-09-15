import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:123@localhost:5432/lenny_growth",
)

from app.models.message import Message
from app.models.session import Session as SessionModel
from app.services.chat import chat_with_transcripts


class InMemoryQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, condition):
        value = condition.right.value
        attribute = condition.left.key
        self.rows = [
            row for row in self.rows if getattr(row, attribute) == value
        ]
        return self

    def order_by(self, ordering):
        self.rows.sort(
            key=lambda row: row.created_at,
            reverse=ordering.modifier.__name__ == "desc_op",
        )
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows


class InMemoryDatabase:
    def __init__(self, sessions):
        self.sessions = sessions
        self.messages = []
        self.pending = []

    def query(self, model):
        rows = self.sessions if model is SessionModel else self.messages
        return InMemoryQuery(rows)

    def add(self, item):
        self.pending.append(item)

    def commit(self):
        self.messages.extend(self.pending)
        self.pending.clear()


class SessionIsolationTest(unittest.TestCase):
    def test_sessions_do_not_share_messages_or_chat_history(self):
        session_a = SessionModel(id=uuid4())
        session_b = SessionModel(id=uuid4())
        db = InMemoryDatabase([session_a, session_b])

        db.add(
            Message(
                session_id=session_a.id,
                role="user",
                content="private session A message",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        )
        db.commit()

        session_b_messages = (
            db.query(Message)
            .filter(Message.session_id == session_b.id)
            .all()
        )
        self.assertEqual(session_b_messages, [])

        captured_prompts = []
        with patch(
            "app.services.agent.search_transcripts",
            return_value=[],
        ), patch(
            "app.services.agent.generate_answer",
            side_effect=lambda **kwargs: captured_prompts.append(
                kwargs["user_prompt"]
            )
            or "The available Lenny transcript material does not provide enough information to answer this confidently.",
        ):
            chat_with_transcripts(
                db=db,
                session_id=session_b.id,
                query="follow-up in session B",
                limit=1,
            )

        self.assertIn("No previous conversation history.", captured_prompts[0])
        self.assertNotIn("private session A message", captured_prompts[0])


if __name__ == "__main__":
    unittest.main()