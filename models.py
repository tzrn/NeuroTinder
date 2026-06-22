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
    prefagefrom = pw.IntegerField(null=True)
    prefageto = pw.IntegerField(null=True)


class Message(Model):
    contents = pw.TextField()
    pic = pw.TextField(null=True)  # uri прикрепленной картики если такова имеется
    user1 = pw.ForeignKeyField(User)
    user2 = pw.ForeignKeyField(User)
    timestamp = pw.DateTimeField(default=datetime.datetime.now, index=True)
    read = pw.BooleanField(default=False)


db.connect()
db.create_tables([User, Message])
