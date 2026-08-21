import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';

export default function ScraperManager() {
  const { fetchWithAuth } = useAuth();
  const [status, setStatus] = useState({ is_running: false });
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState(["[Système] En attente de connexion aux logs..."]);
  const logsEndRef = useRef(null);

  // Remplace par l'URL de ton serveur VNC si tu utilises Docker (voir Étape 3)
  const VNC_CHROME_URL = import.meta.env.VITE_VNC_CHROME_URL;

  // 1. Connexion au WebSocket pour les logs en direct
  useEffect(() => {
    // Adapter le port si ton backend FastAPI tourne sur un autre port (ex: 8000)
    const ws = new WebSocket('ws://localhost:8000/api/scraper/ws/logs');

    ws.onopen = () => {
      setLogs(prev => [...prev, "[Système] Connecté au serveur de logs."]);
    };

    ws.onmessage = (event) => {
      const timestamp = new Date().toLocaleTimeString();
      setLogs(prev => [...prev, `[${timestamp}] ${event.data}`]);
    };

    ws.onclose = () => {
      setLogs(prev => [...prev, "[Système] Déconnecté du serveur de logs."]);
    };

    return () => {
      ws.close();
    };
  }, []);

  // Auto-scroll vers le bas quand un nouveau log arrive
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // 2. Polling du statut
  const fetchStatus = async () => {
    try {
      const res = await fetchWithAuth('/api/scraper/scraper-status');
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (err) {}
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  // 3. Actions
  const handleStartScraping = async () => {
    setLoading(true);
    try {
      await fetchWithAuth('/api/scraper/start-scraping', { method: 'POST' });
      fetchStatus();
    } catch (err) {} finally { setLoading(false); }
  };

  const handleRunPipeline = async () => {
    setLoading(true);
    try {
      await fetchWithAuth('/api/scraper/run-pipeline', { method: 'POST' });
      fetchStatus();
    } catch (err) {} finally { setLoading(false); }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto flex flex-col gap-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-on-surface">Gestionnaire du Scraper</h1>
        </div>
        <div className={`px-4 py-2 rounded-full flex items-center gap-2 font-bold text-sm shadow-sm ${
          status.is_running ? 'bg-secondary-container text-on-secondary-container animate-pulse' : 'bg-surface-container-high text-on-surface-variant'
        }`}>
          <span className="material-symbols-outlined text-lg">
            {status.is_running ? 'settings_motion' : 'stop_circle'}
          </span>
          {status.is_running ? 'Scraper en cours d\'exécution...' : 'Scraper à l\'arrêt'}
        </div>
      </div>

      <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/30 shadow-sm flex flex-wrap gap-4">
        <button onClick={handleStartScraping} disabled={status.is_running || loading} className="flex items-center gap-2 px-5 py-2.5 bg-primary text-on-primary rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50">
          <span className="material-symbols-outlined">web</span> 1. Lancer le Scraper
        </button>
        <button onClick={handleRunPipeline} disabled={status.is_running || loading} className="flex items-center gap-2 px-5 py-2.5 bg-secondary text-on-secondary rounded-lg font-medium hover:bg-secondary/90 disabled:opacity-50">
          <span className="material-symbols-outlined">play_circle</span> 2. Lancer le Pipeline Complet
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Iframe Chrome via VNC */}
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-sm flex flex-col overflow-hidden h-[450px]">
          <div className="bg-surface-container-low p-3 border-b border-outline-variant/20 flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">preview</span>
            <h3 className="font-bold text-sm">Chrome (Vue en direct)</h3>
          </div>
          <div className="flex-1 bg-black relative">
            <iframe src={VNC_CHROME_URL} className="w-full h-full border-none" title="Chrome VNC" />
          </div>
        </div>

        {/* Console de Logs */}
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-sm flex flex-col overflow-hidden h-[450px]">
          <div className="bg-surface-container-low p-3 border-b border-outline-variant/20 flex items-center gap-2">
            <span className="material-symbols-outlined text-secondary">terminal</span>
            <h3 className="font-bold text-sm">Terminal du Serveur</h3>
          </div>
          <div className="flex-1 bg-[#1e1e1e] overflow-y-auto p-4 font-mono text-xs text-green-400 flex flex-col gap-1">
            {logs.map((log, i) => (
              <span key={i}>{log}</span>
            ))}
            <div ref={logsEndRef} /> {/* Point d'ancrage pour l'auto-scroll */}
          </div>
        </div>

      </div>
    </div>
  );
}