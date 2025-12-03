# Contract Extractor API

Локальный сервис извлечения JSON из текста договора (без табличной части). Сервис использует FastAPI, валидирует ответы по JSON Schema и обращается к внешнему демону Ollama, который должен быть запущен отдельно по адресу `http://ollama_android:11434`.

## Внешний сервис Ollama
- API всегда ожидает, что Ollama доступна по `http://ollama_android:11434`. Переменные окружения для изменения адреса больше не поддерживаются.
- По умолчанию используется модель `krith/qwen2.5-32b-instruct:IQ4_XS`. Убедитесь, что она загружена (`ollama pull krith/qwen2.5-32b-instruct:IQ4_XS`).
- Проверьте доступность демона командой `curl http://ollama_android:11434/api/tags`.

Запустить сервис Ollama можно из официального пакета (`ollama serve`) или через Docker (важно использовать host-сеть, чтобы `http://ollama_android:11434` был доступен из контейнера API):

```bash
docker run --rm --network host -v ollama:/root/.ollama ollama/ollama:latest
```

## Контейнеры и образа
- **`api`** — образ FastAPI-сервиса. Собирается напрямую из `python:3.11-slim` без CUDA/torch-слоёв и дополнительных базовых образов.

## Зависимости
- `api/requirements.txt` — единый список зависимостей (FastAPI, Uvicorn, Pydantic, JSON Schema, поддержка multipart, `httpx`, `python-docx`).

Если библиотека не используется в проекте, добавлять её не нужно — лишние пакеты только увеличивают образ.

## Сборка и запуск
1. **Убедитесь, что Ollama запущена**. Проверьте `curl http://ollama_android:11434/api/tags` — ответ должен содержать список моделей. Если демона нет, поднимите его командой `ollama serve` или через Docker (см. выше).

2. **Запустите сервис через Docker Compose**. Достаточно одной команды сборки и старта контейнера:
   ```bash
   docker compose up -d --build
   ```
   После старта API будет доступно на `http://localhost:8085`, Ollama — на `http://ollama_android:11434`.

3. **Изменение модели (опционально)**. Передайте другое имя модели через `MODEL=...` (например, `MODEL=llama3.1`). По умолчанию сервис запрашивает сжатую версию `krith/qwen2.5-32b-instruct:IQ4_XS`.

## Чистый старт Docker-среды
Если нужно пересобрать всё с нуля или избавиться от возможных конфликтов кэша/контейнеров:
```bash
docker compose down --volumes --remove-orphans
docker builder prune --all --force
```
После этого повторите шаги из раздела «Сборка и запуск».

## Добавление зависимостей
После изменения `api/requirements.txt` выполните `docker compose up -d --build`.

## Эндпоинты API
- `GET /healthz` — проверка живости.
- `POST /check` — извлечение данных (принимает текст в `multipart/form-data` или JSON).
- `POST /qa` — задаёт произвольные вопросы по выбранным разделам документа и возвращает агрегированный JSON с ответами.
- `POST /qa/docx` — принимает DOCX-файл, разбивает его на разделы `part_0`, `part_1`, ... и выполняет преднастроенный план вопросов из `api/app/assets/qa_plans/<plan>.json` (по умолчанию `default`).

## Готовые планы вопросов
- Сохраняйте планы в `api/app/assets/qa_plans/<имя>.json`. Формат файла:

  ```json
  {
    "queries": [
      {
        "parts": ["part_0", "part_1"],
        "question": "Определи стороны сделки и о чем они договорились и на какую сумму и с каким НДС",
        "answer": ["buyer", "seller", "review", "sum", "vat"]
      },
      {
        "parts": ["part_0"],
        "question": "Кто ответственственный от покупателя?",
        "answer": ["responsible"]
      }
    ]
  }
  ```

- Вызов `POST /qa/docx?plan=default` примет DOCX-файл, сформирует запрос к LLM вида «Изучи следующие разделы … / И ответь на следующие вопросы …» и вернёт JSON с ответами по ключам из плана.

## Структура проекта
```
api/
  app/
    assets/
      schema.json
    core/
      config.py
      logger.py
      schema.py
      validator.py
    prompts/
      system.txt
      user_template.txt
    services/
      normalize.py
      warnings.py
      utils.py
      compare.py
      ollama_client.py
      extractor/
        base.py
        rules.py
        llm.py
        pipeline.py
  requirements.txt
Dockerfile
docker-compose.yml
```

## План развития
- Расширить регексы и нормализацию по всем полям схемы.
- Добавить few-shot примеры из корпуса эталонов.
- Внедрить дополнительные проверки (даты, суммы, статусы).
- Подключить логи, метрики и трассировку.
