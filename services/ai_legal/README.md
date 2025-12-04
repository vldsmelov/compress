# AI Legal Service

Небольшой сервис FastAPI, адаптированный от эндпойнта `/sections/full`. Он **принимает JSON‑файл, уже нарезанный на секции** (результат `document_slicer`) и возвращает HTML‑отчёт вместе с секциями и спецификацией.

## Эндпойнты
- `POST /api/sections/full` — принимает JSON тела запроса с секциями вида `{\"part_0\": \"...\", ..., \"part_16\": \"...\"}` и возвращает агрегированный HTML‑отчёт вместе с оценками (`overall_score`, `inaccuracy`, `red_flags`).
- `POST /api/sections/full-prepared` — принимает JSON файл секций и возвращает расширенный ответ с секциями, html‑отчётом, полным текстом договора и спецификацией.
- `GET /health` — проверка готовности.

## Интеграция с Ollama
- переменные окружения:
  - `OLLAMA_BASE_URL` — адрес Ollama API (по умолчанию `http://ollama:11434`).
  - `OLLAMA_MODEL` — имя модели (по умолчанию `qwen3:14b`).
- сервис обращается к `/api/chat`, просит модель вернуть JSON с ключами `overall_score`, `summary`, `risks`, `red_flags`, `inaccuracy`. Ответ сохраняется в `ai_summary`, `ai_risks`, `ai_raw_response`, `overall_score`, `inaccuracy`, `red_flags`.