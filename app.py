import logging
import random
from typing import Sequence
import os
from requests import post, get
from sqlalchemy import create_engine, select, func, delete, text
from sqlalchemy.orm import Session
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from collections import defaultdict

from config import HOMEASSISTANT_TOKEN, HOMEASSISTANT_API_URL, SQLALCHEMY_DATABASE_URI, TELEGRAM_BOT_API_TOKEN
from db_models import import_models
from db_models.puzzle import Puzzle
from db_models.team import Team
from db_models.user import User

import_models()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
engine = create_engine(SQLALCHEMY_DATABASE_URI)
PREVIOUS_PUZZLE_ID_KEY = 'current_puzzle_id'


def do_a_print(file_name: str, user=None):
    abs_file_path = f"C:\\Users\\joera\\Development\\scavenger_hunt\\clue.txt"
    new_file_path = f"C:\\Users\\joera\\Development\\scavenger_hunt\\modded.txt"

    if user is not None:
        full_name = f"{user.first_name} {user.last_name}"
        with open(abs_file_path, 'r') as f:
            data = f.read()
            data = data.replace("friend", full_name)

        with open(new_file_path, 'w') as f:
            f.write(data)
            f.close()

    os.startfile(new_file_path, "print")


def check_if_running(location: str) -> dict:
    script_location = "puzzle_first_floor" if location == "First_Floor" else "puzzle_basement"
    url = f"{HOMEASSISTANT_API_URL}states/script.{script_location}"
    response = get(url, headers={"Authorization": f"Bearer {HOMEASSISTANT_TOKEN}"})
    return dict(response.json())


def run_script(location: str, script_name: str, user=None):
    if script_name.startswith("print_"):
        do_a_print(script_name.strip("print_"), user)
    else:
        url = f"{HOMEASSISTANT_API_URL}services/script/turn_on"
        headers = {
            "Authorization": f"Bearer {HOMEASSISTANT_TOKEN}",
            "content-type": "application/json"
        }
        script_location = "puzzle_first_floor" if location == "First_Floor" else "puzzle_basement"
        data = {
            "entity_id": f"script.{script_location}",
            "variables": {
                "script_name": script_name
            }
        }

        response = post(url, headers=headers, json=data)
        return response.text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = update.effective_user

    new_user = User(
        first_name=user_data.first_name,
        id=user_data.id,
        is_bot=user_data.is_bot,
        language_code=user_data.language_code,
        last_name=user_data.last_name,
        username=user_data.username
    )
    if new_user.username is None:
        new_user.username = f"{new_user.first_name}_{new_user.last_name}"

    with Session(engine) as session:
        existing_user = session.scalar(select(User).where(User.id == new_user.id))
        if existing_user is None:
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            response_message = (f"OK {new_user.first_name} {new_user.last_name}, you're all set! You have been "
                                f"registered with the username {new_user.username}")
        else:
            response_message = f"Looks like you're already registered as {existing_user.username} and ready to go!"

        session.close()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)


async def get_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with Session(engine) as session:
        user = get_user_by_id(session, update.effective_user.id)
        my_team = user.team
        my_points = session.scalar(select(func.sum(Puzzle.point_value)).where(Puzzle.completed_by.contains(user)))
        teammates: list[User] = session.scalars(select(User).where(User.team == my_team)).all()
        team_points = defaultdict(int)
        for teammate in teammates:
            cur_team = teammate.team.team
            team_points[cur_team] += sum(puzzle.point_value or 0 for puzzle in teammate.completed_puzzles)
        my_team_points = team_points.pop(my_team.team)
        response_message = f"Your team, the {my_team.team} team, currently has {my_team_points} points, of which you contributed {my_points} points."
        for team, points in team_points.items():
            response_message += f"\n Meanwhile, the {team} team has {points} points."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)
    # with Session(engine) as session:
    #     team_points = get_team_points_dict(session)
    #     user: User = get_user_by_id(session, update.effective_user.id)
    #     my_team = user.team.team
    #     my_points = session.scalar(select(func.sum(Puzzle.point_value)).where(Puzzle.completed_by.contains(user)))
    #     my_team_points = team_points.pop(my_team) if len(team_points) > 0 else 0
    #     response_message = f"Your team, the {my_team} team, currently has {my_team_points} points, of which you contributed {my_points} points."
    #     for team, points in team_points.items():
    #         response_message += f"\n Meanwhile, the {team} team has {points} points."
    #     await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)



async def assign_teams(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username is None or update.effective_user.username != 'joeraver':
        response_message = "Unauthorized"
    else:
        with Session(engine) as session:
            # noinspection SqlWithoutWhere
            session.execute(text("DELETE FROM team_assignment"))
            users: Sequence[User] = session.scalars(select(User)).all()
            i = 0
            teams: Sequence[Team] = session.scalars(select(Team)).all()
            random.shuffle(list(users))
            for user in users:
                user.team = teams[i]
                i += 1
                if i == len(teams):
                    i = 0
            session.commit()
            session.close()
        response_message = "Teams assigned."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)


async def cycle_locations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username is None or update.effective_user.username != 'joeraver':
        response_message = "Unauthorized"
    else:
        with Session(engine) as session:
            teams = list(session.scalars(select(Team)).all())
            first_team_location = teams[0].location
            for i in range(len(teams)):
                j = i + 1
                if j != len(teams):
                    teams[i].location = teams[j].location
                else:
                    teams[i].location = first_team_location
            teams_string = ""
            session.commit()
            for team in teams:
                session.refresh(team)
                teams_string += f"\nThe {team.team} team is now in the {team.location}."
        response_message = f"Teams cycled.{teams_string}"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)


async def my_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with Session(engine) as session:
        team: Team = get_team_by_userid(session, update.effective_user.id)
        response_message = f"You're on the {team.team} team, currently located in the {team.location}"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)


async def running(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username is None or update.effective_user.username != 'joeraver':
        response_message = "Unauthorized"
    else:
        response_message = check_if_running(context.args[0])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)


async def run_script_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username is None or update.effective_user.username != 'joeraver':
        response_message = "Unauthorized"
    else:
        response_message = run_script(context.args[0], context.args[1])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")


async def caps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_caps = ' '.join(context.args).upper()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text_caps)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)


def get_puzzle_by_id(session: Session, id: int) -> Puzzle:
    return session.scalar(select(Puzzle).where(Puzzle.id == id))


def get_puzzle_by_parent_id(session: Session, id: int) -> Puzzle:
    return session.scalar(select(Puzzle).where(Puzzle.parent_puzzle_id == id))


def get_location_by_username(session: Session, username: str) -> str:
    return session.scalar(
        select(Team.location).join(User.team).where(User.username == username))


def get_location_by_userid(session: Session, id: int) -> str:
    return session.scalar(
        select(Team.location).join(User.team).where(User.id == id))


def get_user_by_username(session: Session, username: str) -> User:
    return session.scalar(select(User).where(User.username == username))


def get_user_by_id(session: Session, id: int) -> User:
    return session.scalar(select(User).where(User.id == id))


def get_team_by_username(session: Session, username: str) -> Team:
    return session.scalar(select(User.team).where(User.username == username))


def get_team_by_userid(session: Session, id: int) -> Team:
    user = session.scalar(select(User).where(User.id == id))
    return user.team


def get_team_points_dict(session: Session) -> dict:
    stmt = (select(Team.team, func.sum(Puzzle.point_value))
            .group_by(Team.team).where(Puzzle.completed_by))
    teams = session.execute(stmt).all()
    # noinspection PyTypeChecker
    return dict(teams)


def filter_out_other_team(team: str, completed: list[User]) -> list:
    def same_team(user):
        return user.team == team

    return list(filter(same_team, completed))


async def solve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    previous_puzzle_id = context.user_data.get(PREVIOUS_PUZZLE_ID_KEY)
    guess = update.message.text.strip().lower()
    # By default, assume that the user did not find a puzzle.
    response_message = "Nope! Keep trying!"

    def format_successful_response(pzl: Puzzle) -> str:
        r = pzl.response
        if pzl.point_value and pzl.point_value > 0:
            r = f"Nice job! You received {pzl.point_value} points for your team!\n{r}"
        return r

    with Session(engine) as session:
        location = get_location_by_userid(session, update.effective_user.id)
        user: User = get_user_by_id(session, update.effective_user.id)
        if location is None:
            response_message = "oh, looks like you aren't on a team yet!"
        else:
            puzzle: Puzzle = session.scalar(
                select(Puzzle).where(Puzzle.location == location).where(guess == Puzzle.trigger_word))
            if puzzle is not None:

                def respond_with_success(link_in_chain: bool):
                    next_in_chain: Puzzle = get_puzzle_by_parent_id(session, puzzle.id)
                    if puzzle.script and puzzle.script != "puzzle_stop_media":
                        script = check_if_running(puzzle.location)
                        if script['state'] == 'off':
                            run_script(puzzle.location, str(puzzle.script), user)
                        else:
                            return ("You got the answer to this right, but you'll have to wait for something in "
                                    "the area to finish before solving. Ask if anyone's working on a special puzzle "
                                    "and try sending the same message again after they're done.")
                    if next_in_chain is not None:
                        context.user_data[PREVIOUS_PUZZLE_ID_KEY] = puzzle.id
                    elif link_in_chain:
                        context.user_data.pop(PREVIOUS_PUZZLE_ID_KEY)
                    user.completed_puzzles.add(puzzle)
                    session.commit()

                    return format_successful_response(puzzle)

                completed_by_teammates = filter_out_other_team(user.team.team, puzzle.completed_by)
                if len(completed_by_teammates) > 0:
                    # Puzzle was already solved
                    current_solver: User = completed_by_teammates.pop()
                    response_message = f"Oh looks like this puzzle was already found or is being worked on by {current_solver.first_name} {current_solver.last_name}! Try something else"
                    if previous_puzzle_id:
                        previous_puzzle = get_puzzle_by_id(session, previous_puzzle_id)
                        response_message = response_message + f"\n Here's the info for the puzzle you're currently on: \n{previous_puzzle.response}"
                    #
                    # if current_solver.id == update.effective_user.id:
                    #     response_message = response_message + f"\n And since you are them, here's the info about that puzzle: \n{puzzle.response}"

                elif previous_puzzle_id is None and puzzle.parent_puzzle_id is None:
                    # Start of a new puzzle chain
                    response_message = respond_with_success(False)
                elif previous_puzzle_id is not None and (
                        puzzle.parent_puzzle_id is None or puzzle.parent_puzzle_id != previous_puzzle_id):
                    previous_puzzle = get_puzzle_by_id(session, previous_puzzle_id)
                    # The user probably tried to start at a new puzzle while in the middle of a chain.
                    response_message = (f"Nope! Please note you'll have to finish solving this puzzle chain "
                                        f"before starting another one. Here's the previous puzzle'"
                                        f"s trigger and clue: \n{previous_puzzle.trigger_word} --> \n"
                                        f"{previous_puzzle.response}")
                elif previous_puzzle_id is not None and puzzle.parent_puzzle_id == previous_puzzle_id:
                    # Is the middle or end of a puzzle chain.
                    response_message = respond_with_success(True)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)


FUNNY_COMMAND_RESPONSES = {
    'penis': 'BIG black dick',
    'gay': 'Sorry but homosexual signups are in June.',
    'whore': "OK but now say it like Frank from It's Always Sunny in Philadelphia."
}
FUNNY_COMMANDS = FUNNY_COMMAND_RESPONSES.keys()


async def funny(update: Update, context: ContextTypes.DEFAULT_TYPE):
    funny_word = update.message.text[1:]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=FUNNY_COMMAND_RESPONSES.get(funny_word))


if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_BOT_API_TOKEN).build()

    start_handler = CommandHandler('start', start)
    caps_handler = CommandHandler('caps', caps)
    assign_teams_handler = CommandHandler('assign', assign_teams)
    points_handler = CommandHandler('points', get_points)
    script_handler = CommandHandler('script', run_script_command)
    cycle_handler = CommandHandler('cycle', cycle_locations)
    my_team_handler = CommandHandler(['team', 'teams', 'my_team', 'myteam'], my_team)
    running_handler = CommandHandler('running', running)
    funny_handler = CommandHandler(FUNNY_COMMANDS, funny)

    # echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)
    solve_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), solve)

    application.add_handler(start_handler)
    application.add_handler(caps_handler)
    application.add_handler(solve_handler)
    application.add_handler(assign_teams_handler)
    application.add_handler(points_handler)
    application.add_handler(script_handler)
    application.add_handler(cycle_handler)
    application.add_handler(my_team_handler)
    application.add_handler(running_handler)
    application.add_handler(funny_handler)

    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(unknown_handler)

    application.run_polling()
