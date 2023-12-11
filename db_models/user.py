from __future__ import annotations

from typing import Set, TYPE_CHECKING

from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db_models import Base

if TYPE_CHECKING:
    from db_models.team import Team
    from db_models.puzzle import Puzzle


class User(Base):
    __tablename__ = "user"

    first_name: Mapped[str] = mapped_column(String)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    is_bot: Mapped[bool] = mapped_column(Boolean)
    language_code: Mapped[str] = mapped_column(String)
    last_name: Mapped[str] = mapped_column(String)
    username: Mapped[str] = mapped_column(String, unique=True)
    completed_puzzles: Mapped[Set[Puzzle]] = relationship(secondary="completed", back_populates="completed_by")
    team: Mapped[Team | None] = relationship(secondary="team_assignment", back_populates="members")
