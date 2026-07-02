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
import traceback

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
    request: Request, page: int = Query(None, ge=1), limit: int = Query(3, ge=1, le=5)
):
    user = auth(request.cookies)
    if not user:
        return redir_login

    botsq = (
        models.User.select()
        .where(models.User.isbot)
        .where(
            (models.User.age > user.prefagefrom) & (models.User.age < user.prefageto)
        )
    )

    if page is None:
        page = random.randint(1,len(botsq)//limit)
    bots=botsq.limit(limit + 1).offset((page - 1) * limit)

    hasnew = models.Message.get_or_none((models.Message.user2==user) & (models.Message.read==False)) is not None

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "hasnew": hasnew,
            "username": user.name,
            "pfp": user.pfp,
            "bots": bots[:limit],
            "page": page,
            "has_more": len(bots) == limit + 1,
        },
    )

@app.get("/markread")
async def markread(request: Request):
    user = auth(request.cookies)
    if not user:
        return redir_login
    
    models.Message.update(read=1).where(
        (models.Message.read == 0)
        & (models.Message.user2 == user)
    ).execute()

    return RedirectResponse(url="/chats", status_code=302)

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

    read_case = peewee.Case(
        None,
        [
            (models.Message.user1 == user, 1),
        ],
        default=models.Message.read,
    )

    chats = (
        models.Message.select(models.User, models.Message, read_case.alias("isread"))
        .join(sq, on=(models.Message.id == sq.c.max_id))
        .join(models.User, on=(models.User.id == bot_case))
        .order_by(
            read_case,
            -models.Message.id,
        )
        .limit(limit + 1)
        .offset((page - 1) * limit)
        .dicts()
    )

    return templates.TemplateResponse(
        request=request,
        name="chats.html",
        context={
            "user": user,
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

    models.Message.update(read=1).where(
        (models.Message.read == 0)
        & (models.Message.user1 == bot)
        & (models.Message.user2 == user)
    ).execute()

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
                "num_ctx": 64,
                "temperature": 0.1,
            },
        )
    )["message"]["content"]

    audio = None
    if random.randint(1, 3) == 1:
        audio = str(uuid.uuid4())
        with wave.open(f"./static/audio/{audio}", "wb") as wav_file:
            await asyncio.to_thread(voice.synthesize_wav, resp, wav_file)

    msg = {"from": bot.name, "contents": resp, "audio": audio}
    models.Message.create(contents=resp, user1=bot, user2=user, audio=audio)
    
    if user.id in sockets:
        await sockets[user.id].send_json(msg)


async def handle_socket(ws, user):
    data = await ws.receive_text()
    try:
        j = json.loads(data)
    except json.decoder.JSONDecodeError:
        return

    if "contents" not in j or "bot" not in j:
        return

    bot = models.User.get_or_none(models.User.name == j["bot"])
    if not bot:
        ws.send_text(error("пользователь не найден"))
        ws.close()
        return

    contents = j["contents"]
    models.Message.create(contents=contents, user1=user, user2=bot)

    ctx = context(user, bot)
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

    while True:
        try:
            await handle_socket(websocket, user)
        except Exception as e:
            traceback.print_exc()
            print("deleting connection")
            del sockets[user.id]
            return


def get_random_chat():
    # Пишем только пользователям которые онлайн
    if len(sockets) == 0:
        return None
    userid = random.choice(list(sockets))
    user = models.User.get_or_none(models.User.id == userid)

    bot = None
    if random.randint(1, 4) > 1:
        bot = (
            models.Message.select()
            .where(
                (models.Message.user1 == user) & (models.Message.user2.isbot == True)
            )
            .join(models.User, on=(models.User.id == models.Message.user1.id))
            .group_by(models.Message.user2)
            .order_by(models.db.random())
            .limit(1)
        )
        if len(bot) == 1:
            bot = bot[0].user2
        else:
            bot = None

    if bot is None:
        bot = (
            models.User.select()
            .where(models.User.isbot == True)
            .order_by(models.db.random())
            .limit(1)[0]
        )

    return msg_data(context(user, bot), user, bot)


async def handle_queue():
    while True:
        msg = await msg_queue.get()
        try:
            await reply(msg.ctx, msg.user, msg.bot)
        except Exception:
            traceback.print_exc()
        msg_queue.task_done()


async def produce_messages():
    while True:
        await asyncio.sleep(5)
        if msg_queue._finished.is_set():
            try:
                chat = get_random_chat()
            except Exception:
                traceback.print_exc()
            if chat is not None:
                print(f"messaging {chat.user.name} as {chat.bot.name}")
                await msg_queue.put(chat)
            else:
                print("no connected users found")


@app.on_event("startup")
async def startup_event():
    app.state.queue_worker = asyncio.create_task(handle_queue())
    app.state.producer = asyncio.create_task(produce_messages())
