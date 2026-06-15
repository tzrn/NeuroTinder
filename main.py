from fastapi import FastAPI, Request, Form, Response, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from typing import Annotated

import bcrypt
import secrets
import models


app = FastAPI()
templates = Jinja2Templates(directory="templates")
redir_login = RedirectResponse(url="/static/html/login.html", status_code=302)

app.mount("/static", StaticFiles(directory="static"), name="static")


def verify(name, password, hash):
    return bcrypt.checkpw(password.encode("utf-8"), hash.encode("utf-8"))


def auth(req):
    cookies = req.cookies
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
        return {"error": "Неверный логин или пароль"}

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
        return {"error": "Это имя уже занято"}

    models.User.create(
        name=username,
        password=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()),
        isbot=False,
    )
    return RedirectResponse(url="/static/html/login.html", status_code=302)


@app.get("/home")
async def read_item(
    request: Request, page: int = Query(1, ge=1), limit: int = Query(3, ge=1, le=10)
):
    user = auth(request)
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
