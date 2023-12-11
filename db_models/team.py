from __future__ import annotations

from typing import Set, TYPE_CHECKING

from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db_models import Base
from db_models.puzzle import Puzzle

from db_models.user import User


class Team(Base):
    __tablename__ = "team"

    team: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    location: Mapped[str] = mapped_column(ForeignKey(Puzzle.location))
    members: Mapped[Set[User]] = relationship(secondary="team_assignment", back_populates="team")

