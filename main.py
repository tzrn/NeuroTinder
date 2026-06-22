from fastapi import FastAPI, Request, Form, Response, Query, WebSocket, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from pydantic import StringConstraints
from dataclasses import dataclass
from typing import Annotated

import ollama
import bcrypt
import secrets
import json
import models
import uuid
import peewee
import asyncio
import random

from piper import PiperVoice
import wave

voice = PiperVoice.load("./models/ru_RU-irina-medium.onnx")
app = FastAPI()
templates = Jinja2Templates(directory="templates")
redir_login = RedirectResponse(url="/static/html/login.html", status_code=302)

app.mount("/static", StaticFiles(directory="static"), name="static")


def error(msg):
    return {"error": msg}


def verify(password, hash):
    return bcrypt.checkpw(password.encode("utf-8"), hash.encode("utf-8"))


def auth(cookies):
    user = models.User.get_or_none(models.User.name == cookies.get("username"))
    if user and user.session == cookies.get("session"):
        return user


@app.get("/")
async def root():
    return RedirectResponse(url="/home", status_code=302)


@app.post("/login")
async def login(
    response: Response,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    user = models.User.get_or_none(models.User.name == username)

    if not user or user.isbot or not verify(password, user.password):
        return error("Неверный логин или пароль")

    session = secrets.token_urlsafe(32)
    user.session = session
    user.save()

    response = RedirectResponse(url="/home", status_code=302)
    response.set_cookie(key="username", value=username)
    response.set_cookie(key="session", value=session)
    return response


@app.post("/register")
async def register(
    username: Annotated[str, Form(), StringConstraints(min_length=2, max_length=15)],
    password: Annotated[str, Form(), StringConstraints(min_length=4, max_length=40)],
    prefagefrom: Annotated[int, Form()],
    prefageto: Annotated[int, Form()],
    age: Annotated[int, Form(ge=18, le=130)],
    pfp: Annotated[UploadFile, File()],
):
    user = models.User.get_or_none(models.User.name == username)
    if user:
        return error("Это имя уже занято")

    pfp_filename = uuid.uuid4()
    with open(f"./static/img/pfp/{pfp_filename}", "wb") as f:
        f.write(await pfp.read())

    models.User.create(
        name=username,
        password=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()),
        isbot=False,
        prefagefrom=prefagefrom,
        prefageto=prefageto,
        pfp=pfp_filename,
    )
    return RedirectResponse(url="/static/html/login.html", status_code=302)


@app.get("/home")
async def home(
    request: Request, page: int = Query(1, ge=1), limit: int = Query(3, ge=1, le=5)
):
    user = auth(request.cookies)
    if not user:
        return redir_login

    bots = list(
        models.User.select()
        .where(models.User.isbot)
        .where(
            (models.User.age > user.prefagefrom) & (models.User.age < user.prefageto)
        )
        .limit(limit + 1)
        .offset((page - 1) * limit)
    )
    print(bots)

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "username": user.name,
            "pfp": user.pfp,
            "bots": bots[:limit],
            "page": page,
            "has_more": len(bots) == limit + 1,
        },
    )


@app.get("/chats")
async def chats(
    request: Request, page: int = Query(1, ge=1), limit: int = Query(3, ge=1, le=5)
):
    user = auth(request.cookies)
    if not user:
        return redir_login

    bot_case = (
        peewee.Case(
            None,
            [
                (models.Message.user1 == user, models.Message.user2),
                (models.Message.user2 == user, models.Message.user1),
            ],
        ),
    )

    sq = (
        models.Message.select(peewee.fn.MAX(models.Message.id).alias("max_id"))
        .where((models.Message.user1 == user) | (models.Message.user2 == user))
        .group_by(bot_case)
    )
    print(len(sq.dicts()))

    chats = (
        models.Message.select(models.User, models.Message)
        .join(sq, on=(models.Message.id == sq.c.max_id))
        .join(models.User, on=(models.User.id == bot_case))
        .order_by(-models.Message.id)
        .limit(limit + 1)
        .offset((page - 1) * limit)
        .dicts()
    )

    print(len(chats))

    return templates.TemplateResponse(
        request=request,
        name="chats.html",
        context={
            "chats": chats[:limit],
            "page": page,
            "has_more": len(chats) == limit + 1,
        },
    )


def get_messages(user, bot):
    return (
        models.Message.select()
        .where(
            (models.Message.user1 == user) & (models.Message.user2 == bot)
            | (models.Message.user1 == bot) & (models.Message.user2 == user)
        )
        .order_by(models.Message.id)
    )


def context(user, bot):
    msgs = get_messages(user, bot)
    context = [
        {
            "role": "system",
            "content": f"Do not use emojis. Ты настоящая девушка {bot.age} лет. Тебя зовут {bot.name}. Ответы должны быть короткими.",
        }
    ]
    for m in msgs:
        context.append(
            {
                "role": "assistant" if m.user1 == bot else "user",
                "content": m.contents,
            }
        )
    return context


@app.get("/chat/{username}")
async def chat(request: Request, username: str):
    user = auth(request.cookies)
    if not user:
        return redir_login

    bot = models.User.get_or_none(models.User.name == username)
    if not bot:
        return error("Пользователь не найден")

    messages = get_messages(user, bot)

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={"bot": bot, "user": user, "messages": messages},
    )


sockets = {}
msg_queue = asyncio.Queue()


@dataclass
class msg_data:
    ctx: list[str]
    user: models.User
    bot: models.User


async def reply(context, user, bot):
    resp = (
        await asyncio.to_thread(
            ollama.chat,
            model="qwen3.5:2b-q4_K_M",
            messages=context,
            think=False,
            options={
                "num_predict": 30,
                "num_ctx": 512,
                "temperature": 0.1,
            },
        )
    )["message"]["content"]

    audio = None
    if random.randint(1, 3) == 1:
        audio = str(uuid.uuid4())
        with wave.open(f"./static/audio/{audio}", "wb") as wav_file:
            await asyncio.to_thread(voice.synthesize_wav, resp, wav_file)
        resp = "голосовое сообщение"

    msg = {"contents": resp, "audio": audio}
    models.Message.create(contents=resp, user1=bot, user2=user, audio=audio)

    if user.id in sockets:
        await sockets[user.id].send_json(msg)


async def handle_socket(ws, user, bot, ctx):
    data = await ws.receive_text()
    try:
        j = json.loads(data)
    except json.decoder.JSONDecodeError:
        return

    if "contents" not in j:
        return

    contents = j["contents"]
    models.Message.create(contents=contents, user1=user, user2=bot)
    ctx.append(
        {
            "role": "user",
            "content": contents,
        }
    )

    if bot.id in sockets:
        await sockets[bot.id].send_json({"contents": contents})

    if bot.isbot:
        await msg_queue.put(msg_data(ctx, user, bot))


@app.websocket("/chatws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    user = auth(websocket.cookies)
    if not user:
        websocket.send_text(error("ошибка авторизации"))
        websocket.close()
        return
    sockets[user.id] = websocket

    bot_username = await websocket.receive_text()
    bot = models.User.get_or_none(models.User.name == bot_username)
    if not bot:
        websocket.send_text(error("пользователь не найден"))
        websocket.close()
        return

    ctx = context(user, bot)

    while True:
        try:
            await handle_socket(websocket, user, bot, ctx)
        except:
            print("deleting connection")
            del sockets[user.id]
            return


async def handle_queue():
    while True:
        msg = await msg_queue.get()
        try:
            await reply(msg.ctx, msg.user, msg.bot)
        except Exception as e:
            print(e)
        msg_queue.task_done()


@app.on_event("startup")
async def startup_event():
    app.state.queue_worker = asyncio.create_task(handle_queue())
