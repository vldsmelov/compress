import React from 'react';
import { Hero } from './Hero';
import { ServiceDescriptor } from '../types/services';

interface OverviewPageProps {
  services: ServiceDescriptor[];
  gatewayUrl: string;
}

const flowSteps = [
  'Админ-панель принимает файл и отправляет его в Gateway.',
  'Gateway кладёт задачу в очередь и передаёт её в Aggregator.',
  'Aggregator распараллеливает вызовы в AI-сервисы и собирает ответы.',
  'Результаты и HTML-отчёты возвращаются в панель для просмотра и скачивания.',
];

export function OverviewPage({ services, gatewayUrl }: OverviewPageProps) {
  return (
    <div className="page">
      <Hero
        title="Единая админ-панель"
        subtitle="Современная многопоточность интерфейса: обзор всей платформы, точка входа в Gateway и отдельные страницы под каждый сервис для проверки эндпойнтов."
      />

      <section className="panel panel--stacked">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Документация</p>
            <h2>Как устроена логика приложения</h2>
            <p className="muted">Это главный экран: здесь мы фиксируем поток данных и назначение каждого сервиса, чтобы команда быстро ориентировалась.</p>
          </div>
          <div className="badge badge--outline">Базовый URL Gateway: <span className="mono">{gatewayUrl}</span></div>
        </div>

        <div className="flow-grid">
          {flowSteps.map((step, index) => (
            <div key={step} className="flow-card">
              <div className="flow-card__index">{index + 1}</div>
              <div>
                <p className="flow-card__title">Шаг {index + 1}</p>
                <p className="muted">{step}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel panel--stacked">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Сервисы</p>
            <h2>Что делает каждый сервис</h2>
            <p className="muted">Список формируется автоматически из конфигурации. Перейдите в раздел сервиса, чтобы протестировать эндпойнты.</p>
          </div>
          <div className="chip chip--ghost">{services.length} сервисов</div>
        </div>

        <div className="services-doc-grid">
          {services.map((service) => (
            <article key={service.key} className="service-doc">
              <div className="service-doc__header">
                <div>
                  <p className="eyebrow">{service.name}</p>
                  <h3>{service.summary}</h3>
                </div>
                <span className="badge badge--muted">{service.endpoints.length} эндпойнта</span>
              </div>
              <p className="muted">{service.focus}</p>
              {service.notes && service.notes.length > 0 && (
                <ul className="notes">
                  {service.notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              )}
            </article>
          ))}
        </div>
      </section>

      <section className="panel quickstart">
        <div>
          <p className="eyebrow">Быстрый старт</p>
          <h2>Как проверять эндпойнты и сервисы</h2>
          <p className="muted">1) Выберите сервис в навигации. 2) Укажите путь и тело запроса. 3) Получите ответ и скачайте JSON при необходимости.</p>
        </div>
        <div className="callout">
          <p className="callout__title">Современный UX</p>
          <p className="muted">Переключение страниц не перезагружает состояние — можно параллельно держать открытыми результаты Gateway и консоль конкретного сервиса.</p>
        </div>
      </section>
    </div>
  );
}