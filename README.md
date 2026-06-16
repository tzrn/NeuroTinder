# NeuroTinder

- models.py - код для базы данных
- main.py - сервер
- gendata.py - создать профили ботов

# запуск:
```
uv sync
uv run gendata.py
uv run fastapi dev
```

# todo:
- в чате соединить ботов с LLM, сделать что бы они отправляли катинки
- нагенерировать больше аватарок, создать описания профилей ботов с помощью llm
- ux, css