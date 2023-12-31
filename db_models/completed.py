# User(first_name='Joseph', id=88166700, is_bot=False, language_code='en', last_name='Raver', username='joeraver')
from __future__ import annotations

from sqlalchemy import ForeignKey, Table, Column

from db_models import Base


def _resolve_puzzle_model():
    from db_models.puzzle import Puzzle
    return Puzzle


def _resolve_user_model():
    from db_models.user import User
    return User



completed = Table(
    "completed",
    Base.metadata,
    Column("puzzle_id", ForeignKey(column=_resolve_puzzle_model().id), primary_key=True),
    Column("user_id", ForeignKey(column=_resolve_user_model().id), primary_key=True)
)
