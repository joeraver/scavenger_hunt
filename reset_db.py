import os.path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from db_models import *
from db_models.team import Team
from db_models.user import User

import_models()

cur_dir = os.path.dirname(__file__)
db_path = os.path.join(cur_dir, "scavenger_hunt.db")

engine = create_engine(f"sqlite:///{db_path}")

metadata_obj = Base.metadata
metadata_obj.drop_all(engine)
metadata_obj.create_all(engine)


def run_sql_file(session: Session, sql_file_path):
    with open(sql_file_path) as f:
        lines = f.readlines()
        for j, line in enumerate(lines):
            session.execute(text(line))


with Session(engine) as session:
    red_team = Team(team="Red", location="Basement")
    blue_team = Team(team="Blue", location="First Floor")

    # test_user = User(
    #     first_name="John",
    #     id=9999,
    #     is_bot=False,
    #     language_code='en',
    #     last_name="Smith",
    #     username="johnsmith"
    # )
    session.add_all([red_team, blue_team])

    puzzle_sql_file = os.path.join(cur_dir, "puzzle.sql")
    #run_sql_file(session, puzzle_sql_file)

    session.commit()
    session.close()
