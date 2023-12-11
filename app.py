import logging
from typing import Sequence, Dict
from requests import post
from sqlalchemy.orm import Session
from telegram import Update, InputTextMessageContent, InlineQueryResultArticle
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, InlineQueryHandler
from sqlalchemy import create_engine, select, func
import os
from config import HOMEASSISTANT_TOKEN, HOMEASSISTANT_API_URL, SQLALCHEMY_DATABASE_URI, TELEGRAM_BOT_API_TOKEN
import config
from db_models.puzzle import Puzzle
from db_models.team import Team
from db_models.user import User
from db_models import import_models

import_models()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
engine = create_engine(SQLALCHEMY_DATABASE_URI)
PREVIOUS_PUZZLE_ID = 'current_puzzle_id'


def run_script(script_name: str):
    url = f"{HOMEASSISTANT_API_URL}services/script/turn_on"
    headers = {
        "Authorization": f"Bearer {HOMEASSISTANT_TOKEN}",
        "content-type": "application/json"
    }
    data = {"entity_id": f"script.{script_name}"}

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
        team_points = get_team_points_dict(session)
        user: User = get_user_by_username(session, update.effective_user.username)
        my_team = user.team.team
        my_points = session.scalar(select(func.sum(Puzzle.point_value)).where(Puzzle.completed_by.contains(user)))
        my_team_points = team_points.pop(my_team) if len(team_points) > 0 else 0
        response_message = f"Your team, the {my_team} team, currently has {my_team_points} points, of which you contributed {my_points} points."
        for team, points in team_points.items():
            response_message += f"\n Meanwhile, the {team} team has {points} points."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)


async def assign_teams(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != 'joeraver':
        response_message = "Unauthorized"
    else:
        with Session(engine) as session:
            users: Sequence[User] = session.scalars(select(User)).all()
            i = 0
            teams: Sequence[Team] = session.scalars(select(Team)).all()

            for user in users:
                user.team = teams[i]
                i += 1
                if i == len(teams):
                    i = 0
            session.commit()
            session.close()
        response_message = "Teams assigned."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)


async def run_script_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != 'joeraver':
        response_message = "Unauthorized"
    else:
        response_message = run_script(context.args[0])
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


def get_user_by_username(session: Session, username: str) -> User:
    return session.scalar(select(User).where(User.username == username))


def get_team_by_username(session: Session, username: str) -> Team:
    return session.scalar(select(User.team).where(User.username == username))


def get_team_points_dict(session: Session) -> dict:
    stmt = (select(Team.team, func.sum(Puzzle.point_value))
            .group_by(Team.team).where(Puzzle.completed_by)
            .where(Puzzle.location == Team.location))
    teams = session.execute(stmt).all()
    return dict(teams)


async def solve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    previous_puzzle_id = context.user_data.get(PREVIOUS_PUZZLE_ID)
    guess = update.message.text
    response_message = "Nope! Keep trying!"

    def format_successful_response(puzzle: Puzzle) -> str:
        r = puzzle.response
        if puzzle.point_value > 0:
            r = f"Nice job! You received {puzzle.point_value} points for your team!\n{r}"
        return r

    with Session(engine) as session:
        location = get_location_by_username(session, update.effective_user.username)
        user = get_user_by_username(session, update.effective_user.username)
        if location is None:
            response_message = "oh, looks like you aren't on a team yet!"
        else:
            puzzle: Puzzle = session.scalar(
                select(Puzzle).where(Puzzle.location == location).where(guess == Puzzle.trigger_word))
            if puzzle is not None:
                if len(puzzle.completed_by) > 0:
                    response_message = f"Oh looks like this puzzle was already solved by {puzzle.completed_by.pop().username}!"
                elif previous_puzzle_id is None and puzzle.parent_puzzle_id is None:
                    # if it's the very first valid interaction
                    next_in_chain: Puzzle = get_puzzle_by_parent_id(session, puzzle.id)
                    if next_in_chain is not None:
                        context.user_data[PREVIOUS_PUZZLE_ID] = puzzle.id
                    user.completed_puzzles.add(puzzle)
                    session.commit()
                    response_message = format_successful_response(puzzle)

                elif previous_puzzle_id is not None and (
                        puzzle.parent_puzzle_id is None or puzzle.parent_puzzle_id != previous_puzzle_id):
                    previous_puzzle = get_puzzle_by_id(session, previous_puzzle_id)
                    response_message = (f"Nope! Please note you'll have to finish solving this puzzle chain "
                                        f"before starting another one. Here's the previous puzzle'"
                                        f"s trigger and clue: \n{previous_puzzle.trigger_word} --> \n"
                                        f"{previous_puzzle.response}")
                elif previous_puzzle_id is not None and puzzle.parent_puzzle_id == previous_puzzle_id:
                    # If it's a link in the chain
                    # check if there's another link in the chain and remove the previous puzzle id if
                    next_in_chain: Puzzle = get_puzzle_by_parent_id(session, puzzle.id)
                    if next_in_chain is not None:
                        context.user_data[PREVIOUS_PUZZLE_ID] = puzzle.id
                    else:
                        context.user_data.pop(PREVIOUS_PUZZLE_ID)
                    user.completed_puzzles.add(puzzle)
                    session.commit()
                    response_message = format_successful_response(puzzle)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)


if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_BOT_API_TOKEN).build()

    start_handler = CommandHandler('start', start)
    caps_handler = CommandHandler('caps', caps)
    assign_teams_handler = CommandHandler('assign', assign_teams)
    points_handler = CommandHandler('points', get_points)
    script_handler = CommandHandler('script', run_script_command)

    # echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)
    solve_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), solve)

    application.add_handler(start_handler)
    application.add_handler(caps_handler)
    application.add_handler(solve_handler)
    application.add_handler(assign_teams_handler)
    application.add_handler(points_handler)
    application.add_handler(script_handler)

    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(unknown_handler)

    application.run_polling()
