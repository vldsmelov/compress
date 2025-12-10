# Document splitter microservice

Независимый сервис на FastAPI, который принимает файл договора и возвращает 17 полей `{ "part_0": ..., "part_16": ... }`:

- `part_0`–`part_15` — текст шапки и первых 15 разделов документа в plain text.
- `part_16` — таблица спецификации с тегами `TABLE:`, если она найдена; иначе пустая строка.

Отдельный эндпойнт `/api/specification/parse` возвращает спецификацию в JSON (`spec_json`).

## Запуск через Docker Compose

Фронтенд (`./splitter_frontend`) и сервис секционирования (`./document_slicer`) лежат на одном уровне. Для запуска обоих контейнеров используйте compose-файл из корня репозитория:

```bash
docker compose -f docker-compose.yml up --build
```

- API доступно на `http://localhost:8090`.
- React + TypeScript фронтенд для проверки — `http://localhost:8091`.

## Простой фронтенд для проверки

### Web UI (React)

1. Запустите `docker compose up --build` как описано выше.
2. Откройте `http://localhost:8091`.
3. Загрузите файл договора, нажмите «Отправить», дождитесь ответа.
4. Карточки `part_0`–`part_16` появятся на странице, результат можно скачать кнопкой «Скачать JSON». Спецификация в виде структуры JSON загружается отдельным запросом к `/api/specification/parse` и отображается на той же странице.


## HTTP API

### `POST /api/sections/split`
Загружает файл (`multipart/form-data`, поле `file`) и возвращает JSON с частями документа.

### `POST /api/specification/parse`
Загружает файл (`multipart/form-data`, поле `file`) и возвращает объект `spec_json` с элементами спецификации, итогом и НДС.

Пример тела ответа при успешном выделении спецификации:

```json
{
  "items": [
    {
      "name": "17.3\" Ноутбук ARDOR Gaming RAGE R17-I7ND405 черный",
      "qty": 6,
      "unit": "шт.",
      "price": 152099,
      "amount": 912594,
      "country": "Китай"
    }
  ],
  "total": 912594,
  "vat": 20,
  "warning": null
}
```

### `POST /api/sections/dispatch`
Принимает файл договора, сохраняет секции во внутренний volume (`/data/sections.json` и `/data/part_16.json`) и отправляет их в несколько сервисов.
По умолчанию вызываются `http://ai_econom:10000/analyze`, `/api/sections/full` (контейнер `ai_legal`) и
`http://contract_extractor:8085/qa/sections?plan=default` в общей сети docker-compose.
В контракт-экстрактор отправляются только разделы `part_4`, `part_5`, `part_6`, `part_7`, `part_11`, `part_12`, `part_15`, `part_16` для извлечения реквизитов по плану `default`.
Для анализа подтягивается файл бюджета из volume (`BUDGET_FILE_PATH`, по умолчанию `/data/budget.xlsx`).
Ответ содержит только результаты внешних сервисов в формате `{ "analyze": { ... }, "sections": { ... }, "company": { ... } }`

### `GET /health`
Проверка живости контейнера.