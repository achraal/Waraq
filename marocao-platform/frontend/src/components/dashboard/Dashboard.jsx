import React, { useState } from 'react';
import TelemetryDashboard from './TelemetryDashboard';
import AuditLogsDashboard from './AuditLogsDashboard';
import RAGLogsDashboard from './RAGLogsDashboard';

export default function Dashboard() {
  const [activeView, setActiveView] = useState('telemetry'); // 'telemetry' | 'audit' | 'rag'

  return (
    <div className="w-full text-on-surface flex flex-col gap-6">

      {/* Navigation entre Télémétrie et Audit */}
      <header className="bg-surface-container-low border border-outline/10 p-4 rounded-2xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-xl font-bold font-headline-lg">Console d'Administration & Pilotage</h1>
          <p className="text-body-sm text-on-surface-variant">
            Surveillance des performances, métriques système et journaux d'audit
          </p>
        </div>

        {/* Switcher d'onglets principaux */}
        <nav className="flex gap-2 bg-surface-container p-1 rounded-xl border border-outline/10">
          <button
            onClick={() => setActiveView('telemetry')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-body-sm font-semibold transition-all cursor-pointer ${activeView === 'telemetry'
                ? 'bg-primary text-on-primary shadow-sm'
                : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high'
              }`}
          >
            <span className="material-symbols-outlined text-[18px]">monitoring</span>
            Télémétrie Système
          </button>

          <button
            onClick={() => setActiveView('audit')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-body-sm font-semibold transition-all cursor-pointer ${activeView === 'audit'
                ? 'bg-primary text-on-primary shadow-sm'
                : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high'
              }`}
          >
            <span className="material-symbols-outlined text-[18px]">history_edu</span>
            Journaux d'Audit
          </button>

          <button
            onClick={() => setActiveView('rag')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-body-sm font-semibold transition-all cursor-pointer ${activeView === 'rag'
                ? 'bg-primary text-on-primary shadow-sm'
                : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high'
              }`}
          >
            <span className="material-symbols-outlined text-[18px]">terminal</span>
            Logs RAG
          </button>
        </nav>
      </header>

      {/* Rendu dynamique de la vue sélectionnée */}
      <main className="w-full">
        {activeView === 'telemetry' && <TelemetryDashboard />}
        {activeView === 'audit' && <AuditLogsDashboard />}
        {activeView === 'rag' && <RAGLogsDashboard />}
      </main>
    </div>
  );
}