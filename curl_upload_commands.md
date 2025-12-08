# Памятка по отправке файлов через `curl`

Примеры ниже рассчитаны на новый RabbitMQ-пайплайн. Шлюз (`gateway`) поднимается на `http://localhost:8099` после `docker compose up --build` и принимает DOCX в эндпоинт `/upload`.

## `POST /upload`

Отправьте DOCX-файл, шлюз вернёт агрегированный JSON после прохождения очередей.

```bash
curl -fS -X POST \
  "http://localhost:8099/upload" \
  -H "Accept: application/json" \
  -F "file=@sample/sample_document.docx" \
  | jq
```

Замените `sample/sample_document.docx` на нужный файл. Если нужен текст ошибки сервиса, временно уберите конвейер `| jq` или флаг `-fS`.
