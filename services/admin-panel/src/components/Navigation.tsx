import React from 'react';

interface NavigationItem {
  key: string;
  label: string;
  badge?: string;
}

interface NavigationProps {
  items: NavigationItem[];
  activeKey: string;
  onSelect: (key: string) => void;
}

export function Navigation({ items, activeKey, onSelect }: NavigationProps) {
  return (
    <nav className="nav">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          className={`nav__item ${activeKey === item.key ? 'nav__item--active' : ''}`}
          onClick={() => onSelect(item.key)}
        >
          <span>{item.label}</span>
          {item.badge && <span className="nav__badge">{item.badge}</span>}
        </button>
      ))}
    </nav>
  );
}