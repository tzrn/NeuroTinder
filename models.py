import peewee as pw
import datetime

db = pw.SqliteDatabase("db")


class Model(pw.Model):
    class Meta:
        database = db


class User(Model):
    name = pw.TextField(unique=True)
    pfp = pw.TextField(null=True)  # uri аватарки
    bio = pw.TextField(default="")
    age = pw.IntegerField(null=True)
    password = pw.TextField(null=True)  # хэш
    session = pw.TextField(null=True)
    isbot = pw.BooleanField()


class Message(Model):
    contents = pw.TextField()
    pic = pw.TextField()  # uri прикрепленной картики если такова имеется
    user = pw.ForeignKeyField(User, backref="msgs")
    timestamp = pw.DateTimeField(default=datetime.datetime.now, index=True)


db.connect()
db.create_tables([User])
