import React, { useMemo } from 'react';
import { EndpointDescriptor } from '../types/services';
import { downloadJson } from '../utils/download';

interface EndpointCardProps {
  endpoint: EndpointDescriptor;
  gatewayUrl: string;
  serviceName: string;
}


export function EndpointCard({ endpoint, gatewayUrl, serviceName }: EndpointCardProps) {
  
  const sampleBody = useMemo(() => {
    if (!endpoint.sampleBody) return null;
    return JSON.stringify(endpoint.sampleBody, null, 2);
  }, [endpoint.sampleBody]);

  const curlSnippet = useMemo(() => {
    const lines = [`curl -X ${endpoint.method} ${gatewayUrl}${endpoint.path}`];
    if (endpoint.sampleBody) {
      lines.push('  -H "Content-Type: application/json"');
      lines.push(`  -d '${JSON.stringify(endpoint.sampleBody)}'`);
    }
     return lines.join('\n');
  }, [endpoint.method, endpoint.path, endpoint.sampleBody, gatewayUrl]);

  return (
    <article className="endpoint-card endpoint-card--docs">
      <div className="endpoint-card__header">
        <div className="method" data-method={endpoint.method}>{endpoint.method}</div>
        <div>
          <p className="muted">{serviceName}</p>
          <h3>{endpoint.description}</h3>
          <p className="endpoint-card__path mono">{endpoint.path}</p>
        </div>
      </div>


      <div className="endpoint-card__actions">
        <div className="callout callout--inline">
          <p className="callout__title">Пример вызова</p>
          <pre className="endpoint-card__code mono">{curlSnippet}</pre>
        </div>
        <div className="endpoint-card__buttons endpoint-card__buttons--docs">
          <button type="button" onClick={() => downloadJson(endpoint, `${endpoint.id}.json`)}>
            Скачать описание
          </button>
        </div>
      </div>

      {sampleBody && (
        <div className="field">
          <span className="field__label">Пример тела запроса</span>
          <pre className="code-block">{sampleBody}</pre>
        </div>
      )}
    </article>
  );
}