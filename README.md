# NeuroTinder

- models.py - код для базы данных
- main.py - сервер
- gendata.py - создать профили ботов
- prune.py - удалить похожие аватарки

# использование:
- должны быть установленны ollama (https://ollama.com/download/) и uv (https://docs.astral.sh/uv/getting-started/installation/)
- Что бы скачать аватарки для ботов
```bash
uv pip install gallery-dl
uv run gallery-dl --range "1-50" -o directory="" -d ./static/img/pfp "https://www.pinterest.com/search/pins/?q=2000s%20profile%20picture"
```
- Пока-что для llm используется ollama с qwen3.5:2b-q4_K_M
```bash
ollama serve
ollama pull qwen3.5:2b-q4_K_M
```
- запуск:
```bash
uv sync
uv run gendata.py
uv run fastapi dev
```

# TODO:
- Показывать по одной карточке с возможностью выбора.
- Системная инструкция с примерами.
- Бот может начать/продолжить первым.
- Голосовые сообщения.
