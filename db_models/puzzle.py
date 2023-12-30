# User(first_name='Joseph', id=88166700, is_bot=False, language_code='en', last_name='Raver', username='joeraver')

from typing import Set, TYPE_CHECKING

from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db_models import Base

if TYPE_CHECKING:
    from db_models.user import User


def _resolve_completed_model():
    from db_models.completed import completed
    return completed


class Puzzle(Base):
    __tablename__ = "puzzle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    point_value: Mapped[int] = mapped_column(Integer, nullable=True)
    trigger_word: Mapped[str] = mapped_column(String)
    response: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String)
    script: Mapped[str] = mapped_column(String, nullable=True)
    parent_puzzle_id: Mapped[int] = mapped_column(ForeignKey("puzzle.id"), nullable=True)
    completed_by: Mapped[Set["User"]] = relationship(secondary=lambda: _resolve_completed_model(),
                                                     back_populates="completed_puzzles")
