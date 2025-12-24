import React, { useMemo, useState } from 'react';
import { GatewayResponse } from '../types/api';
import HtmlPreviewModal from './HtmlPreviewModal';
import { downloadHtml, downloadJson } from '../utils/download';
import { Hero } from './Hero';

const HTML_KEYS = ['html', 'html_report', 'report_html', 'document_html'];

interface GatewayConsoleProps {
  gatewayUrl: string;
}

function pickHtml(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null;

  const candidates = [payload as Record<string, unknown>];
  if (typeof (payload as Record<string, unknown>).response === 'object') {
    candidates.push((payload as Record<string, unknown>).response as Record<string, unknown>);
  }

  for (const candidate of candidates) {
    for (const key of HTML_KEYS) {
      const value = candidate?.[key];
      if (typeof value === 'string' && value.trim()) {
        return value;
      }
    }
  }

  return null;
}

function formatServiceName(key: string) {
  const names: Record<string, string> = {
    ai_legal: 'AI Legal',
    ai_econom: 'AI Econom',
    ai_accountant: 'AI Accountant',
    ai_sb: 'AI SB',
    contract_extractor: 'Contract Extractor',
    document_slicer: 'Document Slicer',
    budget_service: 'Budget Service',
  };
  return names[key] || key;
}

export function GatewayConsole({ gatewayUrl }: GatewayConsoleProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GatewayResponse | null>(null);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);

  const serviceEntries = useMemo(() => {
    const payload = result?.result ?? result ?? {};
    return Object.entries(payload).filter(([key]) => key !== 'task_id');
  }, [result]);

  const handleFileSelect = (files: FileList | null) => {
    if (!files?.length) return;
    setFile(files[0]);
    setError(null);
  };

  const handleDrop = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
    handleFileSelect(event.dataTransfer.files);
  };

  const handleUpload = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setResult(null);

    if (!file) {
      setError('Выберите файл договора перед отправкой.');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      setLoading(true);
      const response = await fetch(`${gatewayUrl}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || 'Не удалось отправить документ');
      }

      const data = (await response.json()) as GatewayResponse;
      setResult(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadHtml = (service: string, payload: unknown) => {
    const html = pickHtml(payload);
    if (!html) {
      setError('Для этого сервиса нет HTML отчёта.');
      return;
    }

    downloadHtml(html, `${service}_report.html`);
  };

  const handlePreview = (payload: unknown) => {
    const html = pickHtml(payload);
    if (!html) {
      setError('Для предпросмотра нет HTML отчёта.');
      return;
    }

    setPreviewHtml(html);
  };

  const handleDownloadJson = (service: string, payload: unknown) => {
    downloadJson({ service, payload }, `${service}_response.json`);
  };

  const renderEmptyState = () => (
    <div className="placeholder">
      <p>Результаты появятся после успешной отправки документа в Gateway.</p>
      <p className="placeholder__hint">Мы соберём ответы всех сервисов и покажем их в карточках ниже.</p>
    </div>
  );

  return (
    <div className="page">
      <Hero
        title="Gateway"
        subtitle="Загрузка документов, единый вызов всех подключённых сервисов и моментальный просмотр HTML/JSON-ответов."
      />

      <section className="panel panel--stacked">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Единая точка входа</p>
            <h2>Отправка договора</h2>
            <p className="muted">
              Отправьте файл в очередь Gateway. После выполнения получим task_id и разложим ответы по сервисам.
            </p>
          </div>
          <div className="badge badge--outline">URL: <span className="mono">{gatewayUrl}/upload</span></div>
        </div>

        <form className="upload-form" onSubmit={handleUpload}>
          <label
            className={`dropzone ${isDragging ? 'dropzone--active' : ''}`}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
          >
            <input
              type="file"
              accept=".pdf,.doc,.docx,.txt,.rtf,.json"
              onChange={(event) => handleFileSelect(event.target.files)}
              className="dropzone__input"
            />
            <div className="dropzone__content">
              <div className="dropzone__icon">📄</div>
              <div>
                <p className="dropzone__title">Перетащите файл сюда или нажмите, чтобы выбрать</p>
                <p className="dropzone__hint">Поддерживаются DOCX, PDF, TXT, RTF и JSON.</p>
              </div>
            </div>
          </label>

          <div className="upload-form__footer">
            <div className="chip">{file ? file.name : 'Файл не выбран'}</div>
            <button className="primary" type="submit" disabled={loading}>
              {loading ? 'Отправляем…' : 'Отправить договор'}
            </button>
          </div>
        </form>

        <div className="info-cards">
          <div className="info-card">
            <p className="info-card__title">task_id</p>
            <p className="mono">{result?.task_id ?? 'Появится после загрузки'}</p>
          </div>
          <div className="info-card">
            <p className="info-card__title">Режим</p>
            <p className="muted">Ответ собирается из всех сервисов параллельно.</p>
          </div>
        </div>
      </section>

      {error && <div className="alert alert--error">{error}</div>}

      <section className="panel panel--stacked">
        <div className="results-panel__header">
          <div>
            <p className="eyebrow">Ответы сервисов</p>
            <h2>Сводный результат</h2>
            {result?.task_id && <p className="muted">Task ID: {result.task_id}</p>}
          </div>

          {result && (
            <div className="results-panel__actions">
              <button type="button" onClick={() => setResult(null)}>
                Очистить
              </button>
              <button type="button" onClick={() => downloadJson(result, 'gateway_response.json')}>
                Скачать весь ответ
              </button>
            </div>
          )}
        </div>

        {!serviceEntries.length && renderEmptyState()}

        {!!serviceEntries.length && (
          <div className="services-grid">
            {serviceEntries.map(([service, payload]) => {
              const html = pickHtml(payload);
              const hasError = Boolean((payload as { error?: string })?.error);
              return (
                <article key={service} className="service-card">
                  <header className="service-card__header">
                    <div>
                      <p className="eyebrow">{formatServiceName(service)}</p>
                      <h3>{hasError ? 'Ответ содержит ошибку' : 'Ответ получен'}</h3>
                    </div>
                    <div className={`badge ${hasError ? 'badge--error' : 'badge--success'}`}>
                      {hasError ? 'Ошибка' : 'Готово'}
                    </div>
                  </header>

                  {html && (
                    <div className="service-card__html" dangerouslySetInnerHTML={{ __html: html }} />
                  )}

                  <pre className="service-card__json">{JSON.stringify(payload, null, 2)}</pre>

                  <div className="service-card__actions">
                    <button type="button" onClick={() => handleDownloadJson(service, payload)}>
                      Скачать JSON
                    </button>
                    <button type="button" onClick={() => handlePreview(payload)} disabled={!html}>
                      {html ? 'Открыть HTML' : 'Нет HTML'}
                    </button>
                    <button type="button" onClick={() => handleDownloadHtml(service, payload)} disabled={!html}>
                      Скачать HTML
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      {previewHtml && (
        <HtmlPreviewModal
          html={previewHtml}
          onClose={() => setPreviewHtml(null)}
        />
      )}
    </div>
  );
}