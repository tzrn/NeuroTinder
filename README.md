# NeuroTinder

- models.py - код для базы данных
- main.py - сервер
- gendata.py - создать профили ботов

# использование:
- Что бы скачать аватарки для ботов
```bash
uv pip install gallery-dl
gallery-dl --range "1-50" -o directory="" -d ./static/img/pfp "https://www.pinterest.com/search/pins/?q=selfie%20of%20a%20woman%20social%20media%20low%20light"
```
Пока-что для llm используется ollama с qwen3.5:2b-q4_K_M
```bash
ollama serve
ollama pull qwen3.5:2b-q4_K_M
```
запуск:
```bash
uv sync
uv run gendata.py
uv run fastapi dev
```

# TODO:
- ~~Выбор предпочтений, поле для аватарки~~
- Показывать по одной катачки с возможностью смахивания
- Ротация профилей (каждую ночь удалять 5 и генерировать 5 новых профилей)
- Системная инструкция с примерами.
- Бот может начать/продолжить первым.
- Голосовые сообщения.
