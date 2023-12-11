from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def import_models():
    from db_models.team import Team
    from db_models.user import User
    from db_models.completed import completed
    from db_models.team_assignment import team_assignment
