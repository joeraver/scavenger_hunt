# User(first_name='Joseph', id=88166700, is_bot=False, language_code='en', last_name='Raver', username='joeraver')

from sqlalchemy import ForeignKey, Table, Column

from db_models import Base

team_assignment = Table(
    "team_assignment",
    Base.metadata,
    Column("team", ForeignKey("team.team"), primary_key=True),
    Column("user_id", ForeignKey("user.id"), primary_key=True)
)
