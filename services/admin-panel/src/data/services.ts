import { ServiceDescriptor } from '../types/services';

export const services: ServiceDescriptor[] = [
  {
    key: 'ai_legal',
    name: 'AI Legal',
    summary: 'Юридическая проверка договоров и документов.',
    focus: 'Анализирует риски, проверяет формулировки и формирует HTML‑отчёт по секциям договора.',
    endpoints: [
      {
        id: 'ai-legal-health',
        method: 'GET',
        path: '/api/sections/health',
        description: 'Состояние сервиса и доступность модели Ollama.',
      },
      {
        id: 'ai-legal-evaluate',
        method: 'POST',
        path: '/api/sections/full-prepared',
        description: 'Загрузка файла с готовыми секциями (из document_slicer) для анализа.',
      },
      {
        id: 'ai-legal-full',
        method: 'POST',
        path: '/api/sections/full',
        description: 'Передача секций в теле запроса для юридического анализа.',
        sampleBody: {
          part_1: 'Предмет договора...',
          part_4: 'Порядок оплаты...',
          part_16: 'Цена и НДС...'
        },
      },
    ],
    notes: ['Для /api/sections/full-prepared требуется multipart/form-data с файлом секций.'],
  },
  {
    key: 'ai_econom',
    name: 'AI Econom',
    summary: 'Финансовые и экономические проверки.',
    focus: 'Проверяет бюджетные рамки, согласованность сумм и экономические риски из спецификации.',
    endpoints: [
      {
        id: 'ai-econom-root',
        method: 'GET',
        path: '/',
        description: 'Быстрая проверка работы API и подсказка по доступным маршрутам.',
      },
      {
        id: 'ai-econom-analyze',
        method: 'POST',
        path: '/analyze',
        description: 'Полный анализ спецификации (sections.json) с проверкой бюджетов.',
      },
      {
        id: 'ai-econom-parse',
        method: 'POST',
        path: '/parse-spec',
        description: 'Только парсинг sections.json без проверки бюджетов.',
      },
    ],
    notes: ['Все POST-эндпойнты принимают файл JSON через multipart/form-data.'],
  },
  {
    key: 'ai_accountant',
    name: 'AI Accountant',
    summary: 'Бухгалтерские проверки и сверка спецификаций.',
    focus: 'Сверяет позиции спецификаций, НДС, валюту и формирует JSON с итогами.',
    endpoints: [
      {
        id: 'ai-accountant-health',
        method: 'GET',
        path: '/api/accountant/health',
        description: 'Готовность сервиса и доступность модели Ollama.',
      },
      {
        id: 'ai-accountant-validate',
        method: 'POST',
        path: '/api/accountant/analyze',
        description: 'Проверяет корректность ключевых частей спецификации (part_1, part_4, part_16).',
        sampleBody: {
          part_1: 'Описание предмета договора...',
          part_4: 'Порядок оплаты...',
          part_16: 'Цена и НДС...'
        },
      },
    ],
    notes: ['Для больших спецификаций отправляйте только изменённые строки, чтобы ускорить обработку.'],
  },
  {
    key: 'ai_sb',
    name: 'AI SB',
    summary: 'Проверка служебной безопасности и KYC.',
    focus: 'Работает через очередь sb_queue и публикует результат в aggregation_results.',
    endpoints: [],
    notes: ['HTTP-эндпойнтов нет: сервис запускается как потребитель RabbitMQ.'],
  },
  {
    key: 'contract_extractor',
    name: 'Contract Extractor',
    summary: 'Достаёт факты из договоров.',
    focus: 'Извлекает сроки, суммы и ключевые атрибуты из секций договора.',
    endpoints: [
      {
        id: 'contract-extractor-health',
        method: 'GET',
        path: '/healthz',
        description: 'Быстрая диагностика доступности.',
      },
      {
        id: 'contract-extractor-qa',
        method: 'POST',
        path: '/qa/sections',
        description: 'Запуск плана QA над секциями договора.',
        sampleBody: {
          sections: {
            part_1: 'Предмет договора...',
            part_4: 'Порядок оплаты...'
          }
        },
      },
      {
        id: 'contract-extractor-run-default',
        method: 'POST',
        path: '/qa/run-default',
        description: 'Запуск QA с предустановленным планом default.',
        sampleBody: {
          sections: {
            part_11: 'Срок действия договора до 31.12.2025'
          }
        },
      },
      {
        id: 'contract-extractor-sample',
        method: 'GET',
        path: '/qa/sample-payload',
        description: 'Пример полезной нагрузки для /qa/sections.',
      },
    ],
    notes: ['Для /qa/sections и /qa/run-default требуется JSON с полем sections.'],
  },
  {
    key: 'document_slicer',
    name: 'Document Slicer',
    summary: 'Нарезка документов на логические сегменты.',
    focus: 'Подготавливает текст для других моделей, сохраняя контекст.',
    endpoints: [
      {
        id: 'document-slicer-health',
        method: 'GET',
        path: '/slicer/health',
        description: 'Проверка готовности сервиса.',
      },
      {
        id: 'document-slicer-events',
        method: 'GET',
        path: '/api/timer/events',
        description: 'SSE-поток прогресса для /api/sections/dispatch.',
      },
      {
        id: 'document-slicer-split',
        method: 'POST',
        path: '/api/sections/split',
        description: 'Нарезка секций из загруженного файла (multipart/form-data).',
      },
      {
        id: 'document-slicer-test',
        method: 'POST',
        path: '/test',
        description: 'Простая нарезка без публикации в очереди.',
      },
      {
        id: 'document-slicer-dispatch',
        method: 'POST',
        path: '/api/sections/dispatch',
        description: 'Нарезка секций и отправка задач в очереди RabbitMQ.',
      },
      {
        id: 'document-slicer-dispatch-alias',
        method: 'POST',
        path: '/api/dispatcher',
        description: 'Алиас для dispatch секций с тем же поведением.',
      },
      {
        id: 'document-slicer-time',
        method: 'GET',
        path: '/time',
        description: 'Страница с таймером для визуализации прогресса.',
      },
    ],
    notes: ['Все POST-методы принимают файл через multipart/form-data.'],
  },
  {
    key: 'budget_service',
    name: 'Budget Service',
    summary: 'Расчёт бюджетов и проверка лимитов.',
    focus: 'Сверяет проект с лимитами и сигнализирует о превышениях.',
    endpoints: [
      {
        id: 'budget-service-root',
        method: 'GET',
        path: '/',
        description: 'Служебная проверка доступности и подсказки по маршрутам.',
      },
      {
        id: 'budget-service-check',
        method: 'POST',
        path: '/upload-budget',
        description: 'Загрузка budget.json из 1С (текстовое поле с JSON).',
        sampleBody: {
          budget_json: '[{"КатегорияБюджета":"ИТ","ДоступныйЛимит":1000000}]'
        },
      },
      {
        id: 'budget-service-get',
        method: 'GET',
        path: '/get-budget',
        description: 'Получить текущий budget.json.',
      }
    ],
    notes: ['/upload-budget принимает text/plain: передайте JSON как строку.'],
  },
];