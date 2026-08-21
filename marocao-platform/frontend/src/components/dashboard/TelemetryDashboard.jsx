import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';

// Helper de formatage de la latence LLM (conversion ns / s -> format humain)
const formatLlmLatency = (rawTime) => {
  if (!rawTime || isNaN(rawTime)) return { value: '0', unit: 'ms' };

  let seconds = rawTime > 100000 ? rawTime / 1e9 : rawTime;

  if (seconds < 1) {
    return { value: Math.round(seconds * 1000).toString(), unit: 'ms' };
  } else if (seconds < 60) {
    return { value: seconds.toFixed(2), unit: 's' };
  } else {
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return { value: `${mins}m ${secs}`, unit: 's' };
  }
};

// Composant des 4 cartes KPI principales (Design d'origine conservé)
function TelemetryMetricsCards({ latestMetric, historyMetrics = [], loading = false }) {
  const hw = latestMetric?.server_and_hardware_health || {};
  const db = latestMetric?.database_status || {};
  const aiPipeline = latestMetric?.ai_and_pipeline || {};

  const latency = formatLlmLatency(aiPipeline.temps_moyen);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-[12px]">

      {/* 1. CPU USAGE */}
      <div className="bg-surface-container rounded-xl p-[16px] shadow-sm relative overflow-hidden group">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"></div>
        <div className="flex justify-between items-start mb-[12px]">
          <div className="flex items-center gap-[8px]">
            <span className="material-symbols-outlined text-primary text-[20px]">memory</span>
            <span className="font-body-sm text-body-sm text-on-surface font-semibold">CPU Usage</span>
          </div>
          <span className="bg-surface-container-high px-[6px] py-[2px] rounded font-data-mono text-label-xs text-on-surface-variant">
            {hw.cpu_cores_logical || 0} Cores
          </span>
        </div>
        <div className="flex items-end gap-[12px]">
          <div className="font-data-mono text-[32px] leading-none text-on-background font-bold tracking-tight">
            {loading ? '--' : (hw.cpu_usage_percent ?? 0)}
            <span className="text-[16px] text-on-surface-variant">%</span>
          </div>
          <div className="flex items-center text-secondary mb-[4px] gap-[4px]">
            <span className="material-symbols-outlined text-[16px]">arrow_downward</span>
            <span className="font-data-mono text-label-xs">Active</span>
          </div>
        </div>
        <div className="h-[40px] mt-[16px] w-full">
          <svg className="w-full h-full text-primary" preserveAspectRatio="none" viewBox="0 0 100 40">
            <path d="M0 40 L0 25 L10 20 L20 30 L30 15 L40 25 L50 10 L60 20 L70 5 L80 15 L90 10 L100 20 L100 40 Z" fill="currentColor" fillOpacity="0.1"></path>
            <path d="M0 25 L10 20 L20 30 L30 15 L40 25 L50 10 L60 20 L70 5 L80 15 L90 10 L100 20" fill="none" stroke="currentColor" strokeWidth="2"></path>
          </svg>
        </div>
      </div>

      {/* 2. RAM UTILIZATION */}
      <div className="bg-surface-container rounded-xl p-[16px] shadow-sm relative overflow-hidden group">
        <div className="absolute inset-0 bg-gradient-to-br from-tertiary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"></div>
        <div className="flex justify-between items-start mb-[12px]">
          <div className="flex items-center gap-[8px]">
            <span className="material-symbols-outlined text-tertiary text-[20px]">dns</span>
            <span className="font-body-sm text-body-sm text-on-surface font-semibold">RAM Utilization</span>
          </div>
          <span className="bg-surface-container-high px-[6px] py-[2px] rounded font-data-mono text-label-xs text-on-surface-variant">
            {hw.ram_total_gb || 0}GB Total
          </span>
        </div>
        <div className="flex items-end gap-[12px]">
          <div className="font-data-mono text-[32px] leading-none text-on-background font-bold tracking-tight">
            {loading ? '--' : (hw.ram_used_gb ?? 0)}
            <span className="text-[16px] text-on-surface-variant">GB</span>
          </div>
          <div className="flex items-center text-primary mb-[4px] gap-[4px]">
            <span className="material-symbols-outlined text-[16px]">arrow_upward</span>
            <span className="font-data-mono text-label-xs">{hw.ram_usage_percent || 0}%</span>
          </div>
        </div>
        <div className="mt-[16px] w-full bg-surface-container-highest rounded-full h-[6px] overflow-hidden">
          <div
            className="bg-tertiary h-full rounded-full transition-all duration-500"
            style={{ width: `${hw.ram_usage_percent || 0}%` }}
          ></div>
        </div>
        <div className="flex justify-between mt-[8px]">
          <span className="font-data-mono text-label-xs text-on-surface-variant">{hw.ram_usage_percent || 0}% Used</span>
          <span className="font-data-mono text-label-xs text-on-surface-variant">{hw.ram_available_gb || 0}GB Free</span>
        </div>
      </div>

      {/* 3. POSTGRESQL DB */}
      <div className="bg-surface-container rounded-xl p-[16px] shadow-sm relative overflow-hidden group">
        <div className="absolute inset-0 bg-gradient-to-br from-secondary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"></div>
        <div className="flex justify-between items-start mb-[12px]">
          <div className="flex items-center gap-[8px]">
            <span className="material-symbols-outlined text-secondary text-[20px]">storage</span>
            <span className="font-body-sm text-body-sm text-on-surface font-semibold">PostgreSQL DB</span>
          </div>
          <span className={`px-[6px] py-[2px] rounded font-data-mono text-label-xs ${db.is_connected ? 'bg-secondary-container text-on-secondary-container' : 'bg-error-container text-on-error-container'}`}>
            {db.is_connected ? 'Connected' : 'Offline'}
          </span>
        </div>
        <div className="flex items-end gap-[12px]">
          <div className="font-data-mono text-[32px] leading-none text-on-background font-bold tracking-tight">
            {loading ? '--' : (db.database_size_mb ?? 0)}
            <span className="text-[16px] text-on-surface-variant">MB</span>
          </div>
        </div>
        <div className="mt-[16px] w-full flex h-[16px] rounded overflow-hidden gap-[1px]">
          <div className="bg-secondary w-[50%] h-full flex items-center justify-center">
            <span className="text-[10px] text-on-secondary font-data-mono">{db.tables_count || 0} Tables</span>
          </div>
          <div className="bg-secondary-container w-[35%] h-full flex items-center justify-center">
            <span className="text-[10px] text-on-secondary-container font-data-mono">{db.active_connections || 0} Conn</span>
          </div>
          <div className="bg-surface-container-highest flex-1 h-full flex items-center justify-center">
            <span className="text-[10px] text-on-surface-variant font-data-mono">Active</span>
          </div>
        </div>
        <div className="flex justify-between mt-[8px]">
          <span className="font-data-mono text-label-xs text-on-surface-variant">Top: {db.largest_table || 'N/A'}</span>
          <span className="font-data-mono text-label-xs text-on-surface-variant">{db.largest_table_rows || 0} rows</span>
        </div>
      </div>

      {/* 4. OLLAMA LLM AVG */}
      <div className="bg-surface-container rounded-xl p-[16px] shadow-sm relative overflow-hidden group">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-container/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"></div>
        <div className="flex justify-between items-start mb-[12px]">
          <div className="flex items-center gap-[8px]">
            <span className="material-symbols-outlined text-primary-container text-[20px]">speed</span>
            <span className="font-body-sm text-body-sm text-on-surface font-semibold">Ollama LLM Avg</span>
          </div>
          <span className="bg-surface-container-high px-[6px] py-[2px] rounded font-data-mono text-label-xs text-on-surface-variant">
            Points: {historyMetrics.length || 0}
          </span>
        </div>
        <div className="flex items-end gap-[12px]">
          <div className="font-data-mono text-[32px] leading-none text-on-background font-bold tracking-tight">
            {loading ? '--' : latency.value}
            <span className="text-[16px] text-on-surface-variant">{latency.unit}</span>
          </div>
          <span className="bg-secondary/10 text-secondary px-[6px] py-[2px] rounded font-data-mono text-label-xs mb-[4px]">
            {aiPipeline.tokens_sec ? `${aiPipeline.tokens_sec} tok/s` : 'Optimal'}
          </span>
        </div>
        <div className="h-[40px] mt-[16px] w-full flex items-end gap-[2px]">
          <div className="w-full bg-primary/20 hover:bg-primary transition-colors rounded-t" style={{ height: '60%' }}></div>
          <div className="w-full bg-primary/20 hover:bg-primary transition-colors rounded-t" style={{ height: '80%' }}></div>
          <div className="w-full bg-primary/20 hover:bg-primary transition-colors rounded-t" style={{ height: '40%' }}></div>
          <div className="w-full bg-primary/20 hover:bg-primary transition-colors rounded-t" style={{ height: '90%' }}></div>
          <div className="w-full bg-primary/20 hover:bg-primary transition-colors rounded-t" style={{ height: '70%' }}></div>
          <div className="w-full bg-primary hover:bg-primary transition-colors rounded-t" style={{ height: '50%' }}></div>
          <div className="w-full bg-primary/20 hover:bg-primary transition-colors rounded-t" style={{ height: '100%' }}></div>
          <div className="w-full bg-primary/20 hover:bg-primary transition-colors rounded-t" style={{ height: '30%' }}></div>
          <div className="w-full bg-primary/20 hover:bg-primary transition-colors rounded-t" style={{ height: '60%' }}></div>
          <div className="w-full bg-primary-container transition-colors rounded-t" style={{ height: '45%' }}></div>
        </div>
      </div>

    </div>
  );
}

export default function TelemetryDashboard() {
  const { fetchWithAuth } = useAuth();

  const [latestMetric, setLatestMetric] = useState(null);
  const [historyMetrics, setHistoryMetrics] = useState([]);
  const [allMetrics, setAllMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [activeTab, setActiveTab] = useState('hardware');

  const loadLatestMetrics = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/telemetry/metrics/latest');
      if (res.ok) {
        const data = await res.json();
        setLatestMetric(data);
      }
    } catch (err) {
      console.error("Erreur GET latest metrics:", err);
    }
  }, [fetchWithAuth]);

  const loadHistoryMetrics = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/telemetry/metrics/history?limit=24');
      if (res.ok) {
        const data = await res.json();
        setHistoryMetrics(data.data || []);
      }
    } catch (err) {
      console.error("Erreur GET history metrics:", err);
    }
  }, [fetchWithAuth]);

  const loadAllMetrics = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/telemetry/metrics/all');
      if (res.ok) {
        const data = await res.json();
        setAllMetrics(data.data || []);
      }
    } catch (err) {
      console.error("Erreur GET all metrics:", err);
    }
  }, [fetchWithAuth]);

  const refreshAllTelemetry = useCallback(async () => {
    setLoading(true);
    await Promise.all([
      loadLatestMetrics(),
      loadHistoryMetrics(),
      loadAllMetrics()
    ]);
    setLoading(false);
  }, [loadLatestMetrics, loadHistoryMetrics, loadAllMetrics]);

  useEffect(() => {
    refreshAllTelemetry();
  }, [refreshAllTelemetry]);

  const handleCollectNow = async () => {
    setCollecting(true);
    try {
      const res = await fetchWithAuth('/api/telemetry/collect-now', { method: 'POST' });
      if (res.ok) {
        await refreshAllTelemetry();
      }
    } catch (err) {
      console.error("Erreur POST collect-now:", err);
    } finally {
      setCollecting(false);
    }
  };

  // Mappings dynamiques complets
  const hw = latestMetric?.server_and_hardware_health || {};
  const db = latestMetric?.database_status || {};
  const scraping = latestMetric?.scraping_metrics || {};
  const aiMetrics = latestMetric?.ai_metrics || {};
  const aiPipeline = latestMetric?.ai_and_pipeline || {};

  return (
    <div className="flex flex-col w-full p-6 gap-6 bg-surface text-on-surface">
      {/* En-tête */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="font-headline-lg text-2xl font-bold">System Telemetry Center</h1>
          <p className="text-body-sm text-on-surface-variant">
            Dernier snapshot enregistré : <span className="font-data-mono font-semibold">{latestMetric?.timestamp ? new Date(latestMetric.timestamp).toLocaleString() : 'Aucun'}</span>
          </p>
        </div>

        <button
          onClick={handleCollectNow}
          disabled={collecting}
          className="flex items-center gap-2 bg-primary text-on-primary px-4 py-2 rounded-xl text-body-sm font-semibold hover:opacity-90 transition-all disabled:opacity-50 cursor-pointer shadow-sm"
        >
          <span className={`material-symbols-outlined text-[18px] ${collecting ? 'animate-spin' : ''}`}>
            refresh
          </span>
          {collecting ? 'Collecte en cours...' : 'Forcer la collecte (Collect Now)'}
        </button>
      </div>

      {/* Cartes KPI Principales */}
      <TelemetryMetricsCards
        latestMetric={latestMetric}
        historyMetrics={historyMetrics}
        loading={loading}
      />

      {/* Onglets d'exploration des détails */}
      <div className="flex gap-2 border-b border-outline/10 pb-2 overflow-x-auto">
        {[
          { id: 'hardware', label: 'Server & Hardware' },
          { id: 'db', label: 'Database Status' },
          { id: 'scraping', label: 'Scraping Metrics' },
          { id: 'ai', label: 'AI & Pipeline LLM' },
          { id: 'history', label: `Historique complet (${allMetrics.length})` }
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg text-body-sm font-semibold transition-all cursor-pointer whitespace-nowrap ${activeTab === tab.id
                ? 'bg-primary text-on-primary'
                : 'bg-surface-container-low hover:bg-surface-container text-on-surface-variant'
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* VUE 1 : HARDWARE & PROCESS FASTAPI */}
      {activeTab === 'hardware' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-surface-container-low p-4 rounded-xl border border-outline/10 space-y-3">
            <h3 className="font-bold text-body-md">Statistiques Hôte & Système</h3>
            <div className="space-y-2 text-body-sm font-data-mono">
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Utilisation CPU :</span><span className="font-bold">{hw.cpu_usage_percent ?? 0}%</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Cœurs Logiques / Physiques :</span><span>{hw.cpu_cores_logical ?? 0} / {hw.cpu_cores_physical ?? 0}</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>RAM Utilisée / Totale :</span><span>{hw.ram_used_gb ?? 0} GB / {hw.ram_total_gb ?? 0} GB</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>RAM Disponible :</span><span>{hw.ram_available_gb ?? 0} GB</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Disque Utilisé :</span><span>{hw.disk_usage_percent ?? 0}% ({hw.disk_free_gb ?? 0} GB Libres / {hw.disk_total_gb ?? 0} GB)</span></div>
            </div>
          </div>

          <div className="bg-surface-container-low p-4 rounded-xl border border-outline/10 space-y-3">
            <h3 className="font-bold text-body-md">Processus FastAPI Spécifique</h3>
            <div className="space-y-2 text-body-sm font-data-mono">
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Mémoire RSS FastAPI :</span><span className="font-bold">{hw.fastapi_memory_rss_mb ?? 0} MB</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Fichiers / Sockets ouverts :</span><span>{hw.fastapi_open_files ?? 0}</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Uptime Serveur :</span><span>{hw.fastapi_uptime_seconds ?? 0} secondes</span></div>
            </div>
          </div>
        </div>
      )}

      {/* VUE 2 : DATABASE METRICS */}
      {activeTab === 'db' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-surface-container-low p-3 rounded-lg border border-outline/10">
              <div className="text-label-xs text-on-surface-variant">Table la plus volumineuse</div>
              <div className="text-body-md font-bold font-data-mono">{db.largest_table || 'N/A'}</div>
              <div className="text-label-xs text-primary font-data-mono">{db.largest_table_rows || 0} lignes</div>
            </div>
            <div className="bg-surface-container-low p-3 rounded-lg border border-outline/10">
              <div className="text-label-xs text-on-surface-variant">Taille BDD Totale</div>
              <div className="text-body-md font-bold font-data-mono">{db.database_size_mb ?? 0} MB</div>
            </div>
            <div className="bg-surface-container-low p-3 rounded-lg border border-outline/10">
              <div className="text-label-xs text-on-surface-variant">Connexions Actives</div>
              <div className="text-body-md font-bold font-data-mono">{db.active_connections ?? 0}</div>
            </div>
            <div className="bg-surface-container-low p-3 rounded-lg border border-outline/10">
              <div className="text-label-xs text-on-surface-variant">Dernier Backup</div>
              <div className="text-body-md font-bold font-data-mono">{db.last_backup ? new Date(db.last_backup).toLocaleString() : 'N/A'}</div>
            </div>
          </div>

          <div className="bg-surface-container-low p-4 rounded-xl border border-outline/10">
            <h3 className="font-bold text-body-md mb-3">Répartition des lignes par table (`rows_per_table`)</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 font-data-mono text-label-xs">
              {db.rows_per_table && Object.entries(db.rows_per_table).map(([table, count]) => (
                <div key={table} className="p-2 bg-surface rounded border border-outline/10 flex justify-between">
                  <span className="truncate">{table}</span>
                  <span className="font-bold text-primary">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* VUE 3 : SCRAPING METRICS */}
      {activeTab === 'scraping' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-surface-container-low p-4 rounded-xl border border-outline/10 space-y-3">
            <h3 className="font-bold text-body-md">Activité du Scraper Aujourd'hui</h3>
            <div className="space-y-2 text-body-sm font-data-mono">
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Total Documents Scrapés :</span><span className="font-bold">{scraping.total_scraped_today ?? 0}</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Documents Téléchargés :</span><span>{scraping.docs_downloaded_today ?? 0}</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Tenders Scrapés :</span><span>{scraping.tenders_scraped_today ?? 0}</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Fichiers ZIP Téléchargés :</span><span>{scraping.zips_downloaded_today ?? 0}</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Emails Reçus / Traités :</span><span>{scraping.emails_received_today ?? 0} / {scraping.emails_processed_today ?? 0}</span></div>
            </div>
          </div>

          <div className="bg-surface-container-low p-4 rounded-xl border border-outline/10 space-y-3">
            <h3 className="font-bold text-body-md">Santé & Performance du Scraper</h3>
            <div className="space-y-2 text-body-sm font-data-mono">
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>État du Scraper Chrome/Driver :</span><span className={scraping.scraper_running ? 'text-primary font-bold' : 'text-on-surface-variant'}>{scraping.scraper_running ? 'En cours (Running)' : 'Inactif'}</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Durée Moyenne de Scraping :</span><span>{scraping.avg_scraping_duration_sec ?? 0} sec</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Taux de Succès :</span><span className="font-bold text-primary">{scraping.success_rate ?? 100}%</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Échecs de Scraping :</span><span className="text-error">{scraping.failed_scraping ?? 0}</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Erreurs Selenium Totales :</span><span className="text-error">{scraping.selenium_errors_total ?? 0}</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>ZIPs Corrompus Totaux :</span><span className="text-error">{scraping.corrupted_zips_total ?? 0}</span></div>
              <div className="flex justify-between border-b border-outline/10 pb-1"><span>Statut Sync / Dernier Scraping :</span><span>{scraping.last_sync_status || 'N/A'} ({scraping.last_scraping ? new Date(scraping.last_scraping).toLocaleString() : 'N/A'})</span></div>
            </div>
          </div>
        </div>
      )}

      {/* VUE 4 : AI & PIPELINE METRICS (AFFICHAGE COMPLET DE TOUTES LES DONNÉES) */}
      {activeTab === 'ai' && (
        <div className="space-y-4">
          {/* Ligne 1 : Jetons & Précision Métier */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-surface-container-low p-4 rounded-xl border border-outline/10 space-y-2">
              <h4 className="font-bold text-body-sm text-on-surface-variant">Volumes & Précision LLM</h4>
              <div className="text-label-xs font-data-mono space-y-1">
                <div className="flex justify-between"><span>Inférences Historiques Totales:</span><span>{aiPipeline.total_classifications ?? aiMetrics.total_inferences_historical ?? 0}</span></div>
                <div className="flex justify-between"><span>Inférences Aujourd'hui:</span><span>{aiMetrics.volumes?.today ?? 0}</span></div>
                <div className="flex justify-between"><span>Précision IA (Accuracy):</span><span className="text-primary font-bold">{aiPipeline.accuracy_ia ?? 100}%</span></div>
                <div className="flex justify-between"><span>Confiance Moyenne:</span><span>{aiPipeline.confidence_moyenne ?? 0}</span></div>
                <div className="flex justify-between"><span>Taux de Correction Humaine:</span><span className="text-error">{aiPipeline.validation?.taux_de_correction ?? 0}%</span></div>
              </div>
            </div>

            <div className="bg-surface-container-low p-4 rounded-xl border border-outline/10 space-y-2">
              <h4 className="font-bold text-body-sm text-on-surface-variant">Temps & Jetons (LLM/Ollama)</h4>
              <div className="text-label-xs font-data-mono space-y-1">
                <div className="flex justify-between"><span>Prompt / Generated Tokens:</span><span>{aiPipeline.tokens?.prompt ?? 0} / {aiPipeline.tokens?.generated ?? 0}</span></div>
                <div className="flex justify-between"><span>Total Tokens:</span><span>{aiPipeline.tokens?.total ?? 0}</span></div>
                <div className="flex justify-between text-primary font-bold"><span>Débit Jetons:</span><span>{aiPipeline.tokens_sec ?? 0} tok/s</span></div>
                <div className="flex justify-between"><span>Temps / Token:</span><span>{aiPipeline.temps_par_token_ms ?? 0} ms</span></div>
                <div className="flex justify-between"><span>Pipeline Min / Max / Avg:</span><span>{aiPipeline.temps_mini ?? 0}s / {aiPipeline.temps_maxi ?? 0}s / {aiPipeline.pipeline_moyen ?? 0}s</span></div>
              </div>
            </div>

            <div className="bg-surface-container-low p-4 rounded-xl border border-outline/10 space-y-2">
              <h4 className="font-bold text-body-sm text-on-surface-variant">Validation des Inférences</h4>
              <div className="text-label-xs font-data-mono space-y-1">
                <div className="flex justify-between"><span>Validés (VALIDATED):</span><span className="text-primary font-bold">{aiPipeline.validation?.VALIDATED ?? 0}</span></div>
                <div className="flex justify-between"><span>Corrigés (CORRECTED):</span><span className="text-error font-bold">{aiPipeline.validation?.CORRECTED ?? 0}</span></div>
                <div className="flex justify-between"><span>En attente (PENDING):</span><span>{aiPipeline.validation?.PENDING ?? 0}</span></div>
                <div className="flex justify-between"><span>Part OCR / Native Text:</span><span>{aiPipeline.ocr_percent ?? 0}% / {100 - (aiPipeline.ocr_percent ?? 0)}%</span></div>
                <div className="flex justify-between"><span>Documents Mixtes:</span><span>{aiPipeline.documents_mixtes ?? 0}</span></div>
              </div>
            </div>
          </div>

          {/* Ligne 2 : Statistiques Avancées Fichiers & Répartitions (Types / Langues) */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-surface-container-low p-4 rounded-xl border border-outline/10 space-y-2">
              <h4 className="font-bold text-body-sm text-on-surface-variant">Statistiques Fichiers PDF</h4>
              <div className="text-label-xs font-data-mono space-y-1">
                <div className="flex justify-between"><span>Pages Moyennes:</span><span>{aiPipeline.documents_stats?.pages_moyennes ?? 0}</span></div>
                <div className="flex justify-between"><span>Mots Moyens / Doc:</span><span>{aiPipeline.documents_stats?.mots_moyens ?? 0}</span></div>
                <div className="flex justify-between"><span>Taille Moyenne:</span><span>{aiPipeline.documents_stats?.taille_moyenne_mb ?? 0} MB</span></div>
                <div className="flex justify-between"><span>Plus Gros Document:</span><span>{aiPipeline.documents_stats?.plus_gros_document_mb ?? 0} MB</span></div>
                <div className="flex justify-between"><span>OCR / LLM Max Sec:</span><span>{aiPipeline.documents_stats?.plus_long_ocr_sec ?? 0}s / {aiPipeline.documents_stats?.plus_long_llm_sec ?? 0}s</span></div>
              </div>
            </div>

            <div className="bg-surface-container-low p-4 rounded-xl border border-outline/10 space-y-2">
              <h4 className="font-bold text-body-sm text-on-surface-variant">Types de Documents Prédits</h4>
              <div className="text-label-xs font-data-mono space-y-1 max-h-[140px] overflow-y-auto">
                {aiPipeline.types_detectes && Object.entries(aiPipeline.types_detectes).length > 0 ? (
                  Object.entries(aiPipeline.types_detectes).map(([type, count]) => (
                    <div key={type} className="flex justify-between border-b border-outline/5 pb-1">
                      <span>{type}:</span>
                      <span className="font-bold text-primary">{count}</span>
                    </div>
                  ))
                ) : (
                  <div className="text-on-surface-variant">Aucune donnée</div>
                )}
              </div>
            </div>

            <div className="bg-surface-container-low p-4 rounded-xl border border-outline/10 space-y-2">
              <h4 className="font-bold text-body-sm text-on-surface-variant">Répartition par Langues</h4>
              <div className="text-label-xs font-data-mono space-y-1 max-h-[140px] overflow-y-auto">
                {aiPipeline.langues && Object.entries(aiPipeline.langues).length > 0 ? (
                  Object.entries(aiPipeline.langues).map(([lang, count]) => (
                    <div key={lang} className="flex justify-between border-b border-outline/5 pb-1">
                      <span>{lang}:</span>
                      <span className="font-bold">{count}</span>
                    </div>
                  ))
                ) : (
                  <div className="text-on-surface-variant">Aucune donnée</div>
                )}
              </div>
            </div>
          </div>

          {/* Ligne 3 : Historique journalier des 7 derniers jours */}
          {aiPipeline.volumes_historique?.historique_journalier && (
            <div className="bg-surface-container-low p-4 rounded-xl border border-outline/10 space-y-2">
              <h4 className="font-bold text-body-sm text-on-surface-variant">Historique Journalier des Inférences (7 Derniers Jours)</h4>
              <div className="grid grid-cols-2 md:grid-cols-7 gap-2 font-data-mono text-label-xs">
                {Object.entries(aiPipeline.volumes_historique.historique_journalier).map(([jour, total]) => (
                  <div key={jour} className="p-2 bg-surface rounded border border-outline/10 flex flex-col items-center">
                    <span className="text-on-surface-variant">{jour}</span>
                    <span className="font-bold text-primary text-body-md mt-1">{total}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* VUE 5 : HISTORIQUE COMPLET */}
      {activeTab === 'history' && (
        <div className="bg-surface rounded-xl border border-outline/10 overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container-low text-label-xs uppercase">
                <th className="p-3">Timestamp</th>
                <th className="p-3">CPU %</th>
                <th className="p-3">RAM (GB)</th>
                <th className="p-3">DB Size</th>
                <th className="p-3">Docs Scrapés aujourd'hui</th>
                <th className="p-3">Avg Ollama</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline/5 text-body-sm font-data-mono">
              {allMetrics.length === 0 ? (
                <tr><td colSpan="6" className="p-4 text-center">Aucun historique disponible.</td></tr>
              ) : (
                allMetrics.map((item) => {
                  const itemLatency = formatLlmLatency(item.ai_and_pipeline?.temps_moyen);
                  return (
                    <tr key={item.id} className="hover:bg-surface-container/50">
                      <td className="p-3">{new Date(item.timestamp).toLocaleString()}</td>
                      <td className="p-3">{item.server_and_hardware_health?.cpu_usage_percent ?? 0}%</td>
                      <td className="p-3">{item.server_and_hardware_health?.ram_used_gb ?? 0} GB</td>
                      <td className="p-3">{item.database_status?.database_size_mb ?? 0} MB</td>
                      <td className="p-3">{item.scraping_metrics?.total_scraped_today ?? 0}</td>
                      <td className="p-3">{itemLatency.value}{itemLatency.unit}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}