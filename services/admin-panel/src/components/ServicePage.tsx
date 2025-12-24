import React from 'react';
import { ServiceDescriptor } from '../types/services';
import { Hero } from './Hero';
import { EndpointCard } from './EndpointCard';

interface ServicePageProps {
  service: ServiceDescriptor;
  gatewayUrl: string;
}

export function ServicePage({ service, gatewayUrl }: ServicePageProps) {
  return (
    <div className="page">
      <Hero
        title={service.name}
        subtitle={service.focus}
      />

      <section className="panel panel--stacked">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Документация сервиса</p>
            <h2>{service.summary}</h2>
            <p className="muted">Здесь собраны описания эндпойнтов и примеры вызовов.</p>
          </div>
          <div className="chip chip--ghost">{service.endpoints.length} эндпойнта</div>
        </div>

        {service.notes && service.notes.length > 0 && (
          <div className="notes notes--spaced">
            {service.notes.map((note) => (
              <div key={note} className="note-pill">{note}</div>
            ))}
          </div>
        )}
      </section>

      <div className="endpoint-grid">
        {service.endpoints.map((endpoint) => (
          <EndpointCard
            key={endpoint.id}
            endpoint={endpoint}
            gatewayUrl={gatewayUrl}
            serviceName={service.name}
          />
        ))}
      </div>
    </div>
  );
}