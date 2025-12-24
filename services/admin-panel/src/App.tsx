import React, { useMemo, useState } from 'react';
import { GatewayConsole } from './components/GatewayConsole';
import { OverviewPage } from './components/OverviewPage';
import { ServicePage } from './components/ServicePage';
import { Navigation } from './components/Navigation';
import { services } from './data/services';

const DEFAULT_GATEWAY_URL = 'http://localhost:8099';

type PageKey = 'overview' | 'gateway' | string;

function resolveGatewayUrl() {
  const envUrl = import.meta.env.VITE_GATEWAY_URL as string | undefined;
  return (envUrl && envUrl.trim()) || DEFAULT_GATEWAY_URL;
}


export default function App() {
  const gatewayUrl = useMemo(resolveGatewayUrl, []);
  const [activePage, setActivePage] = useState<PageKey>('overview');
  const navItems = [
    { key: 'overview', label: 'Обзор' },
    { key: 'gateway', label: 'Gateway' },
    ...services.map((service) => ({ key: service.key, label: service.name, badge: `${service.endpoints.length}` })),
  ];
  const activeService = services.find((service) => service.key === activePage);  

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="logo">Admin Panel</div>
        <p className="sidebar__hint">Мониторинг и проверка эндпойнтов всех сервисов. Базовый URL: <span className="mono">{gatewayUrl}</span></p>
        <Navigation items={navItems} activeKey={activePage} onSelect={setActivePage} />
      </aside>

      <main className="content">
        {activePage === 'overview' && <OverviewPage services={services} gatewayUrl={gatewayUrl} />}
        {activePage === 'gateway' && <GatewayConsole gatewayUrl={gatewayUrl} />}
        {activeService && <ServicePage service={activeService} gatewayUrl={gatewayUrl} />}
      </main>
    </div>
  );
}