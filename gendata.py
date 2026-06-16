import models
import os
import random

files = os.listdir("static/img/pfp")
fnames = ["Анна", "Ольга", "Жасмин", "Анастасия", "Злата"]
lnames = ["Кузнецова", "Игоревна", "Крафт"]

for i in fnames:
    for j in lnames:
        models.User.create(
            name=i + j,
            password="",
            pfp=random.choice(files),
            isbot=True,
            age=random.randint(18, 40),
            bio="ищу",
        )
