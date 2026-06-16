from fastapi import FastAPI, Request, Form, Response, Query, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from typing import Annotated

import ollama
import bcrypt
import secrets
import json
import models


app = FastAPI()
templates = Jinja2Templates(directory="templates")
redir_login = RedirectResponse(url="/static/html/login.html", status_code=302)

app.mount("/static", StaticFiles(directory="static"), name="static")


def error(msg):
    return {"error": msg}


def verify(name, password, hash):
    return bcrypt.checkpw(password.encode("utf-8"), hash.encode("utf-8"))


def auth(cookies):
    user = models.User.get_or_none(models.User.name == cookies.get("username"))
    if user and user.session == cookies.get("session"):
        return user


@app.get("/")
async def root():
    return redir_login


@app.post("/login")
async def login(
    response: Response,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    user = models.User.get_or_none(models.User.name == username)

    if not user or user.isbot or not verify(username, password, user.password):
        return error("Неверный логин или пароль")

    session = secrets.token_urlsafe(32)
    user.session = session
    user.save()

    response = RedirectResponse(url="/home", status_code=302)
    response.set_cookie(key="username", value=username)
    response.set_cookie(key="session", value=session)
    return response


@app.post("/register")
async def register(username: Annotated[str, Form()], password: Annotated[str, Form()]):
    user = models.User.get_or_none(models.User.name == username)
    if user:
        return error("Это имя уже занято")

    models.User.create(
        name=username,
        password=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()),
        isbot=False,
    )
    return RedirectResponse(url="/static/html/login.html", status_code=302)


@app.get("/home")
async def read_item(
    request: Request, page: int = Query(1, ge=1), limit: int = Query(3, ge=1, le=5)
):
    user = auth(request.cookies)
    if not user:
        return redir_login

    bots = list(
        models.User.select()
        .where(models.User.isbot)
        .limit(limit + 1)
        .offset((page - 1) * limit)
    )
    print(bots)

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "username": user.name,
            "bots": bots[:limit],
            "page": page,
            "has_more": len(bots) == limit + 1,
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
            "content": f"You're {bot.age} year old woman. Replies must be short.",
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


async def reply(ws, context, user, bot):
    resp = ollama.chat(
        model="qwen3.5:0.8b",
        messages=context,
        think=False,
        options={
            "num_predict": 20,
            "num_ctx": 512,
            "temperature": 0.7,
        },
    )["message"]["content"]
    print(resp)
    msg = '{"contents":"' + resp + '"}'
    models.Message.create(contents=resp, user1=bot, user2=user)
    await ws.send_text(msg)


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
        return error("Пользователь не найден")

    ctx = context(user, bot)

    while True:
        data = await websocket.receive_text()
        try:
            j = json.loads(data)
        except json.decoder.JSONDecodeError:
            continue

        if "contents" not in j:
            continue

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
            await reply(websocket, ctx, user, bot)
