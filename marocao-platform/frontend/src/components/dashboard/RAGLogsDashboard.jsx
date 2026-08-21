import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function RAGLogsDashboard() {
  const { fetchWithAuth } = useAuth();

  // États pour les données
  const [stats, setStats] = useState(null);
  const [tenderStats, setTenderStats] = useState(null); // Stats spécifiques à un Tender
  const [logs, setLogs] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedLog, setSelectedLog] = useState(null);

  // États de filtrage & pagination
  const [levelFilter, setLevelFilter] = useState('');
  const [stageFilter, setStageFilter] = useState('');
  const [searchTenderId, setSearchTenderId] = useState('');
  const [searchDocumentId, setSearchDocumentId] = useState(''); // Recherche par Document UUID
  const [skip, setSkip] = useState(0);
  const limit = 15;

  // États de chargement
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);

  // Helper pour formater la durée (secondes vs minutes)
  const formatDuration = (seconds) => {
    if (seconds === null || seconds === undefined) return '--';
    if (seconds >= 60) {
      const mins = Math.floor(seconds / 60);
      const secs = (seconds % 60).toFixed(1);
      return `${mins}m ${secs}s`;
    }
    return `${seconds.toFixed(2)}s`;
  };

  // 1. GET /api/rag/stats (Stats globales)
  const fetchStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      const res = await fetchWithAuth('/api/rag/stats');
      if (res.ok) setStats(await res.json());
    } catch (err) {
      console.error("Erreur GET /api/rag/stats :", err);
    } finally {
      setLoadingStats(false);
    }
  }, [fetchWithAuth]);

  // 2. Fetch Logs (Supporte la liste, /tender/{id}, /document/{id} et /stats/{tender_id})
  const fetchLogs = useCallback(async () => {
    setLoadingLogs(true);
    setTenderStats(null); // Reset des stats tender si changement de filtre

    try {
      // Cas A : Filtrage par Tender ID + Récupération des stats du Tender
      if (searchTenderId.trim()) {
        const [logsRes, statsRes] = await Promise.all([
          fetchWithAuth(`/api/rag/tender/${searchTenderId.trim()}`),
          fetchWithAuth(`/api/rag/stats/${searchTenderId.trim()}`)
        ]);

        if (logsRes.ok) {
          const data = await logsRes.json();
          setLogs(data || []);
          setTotalCount(data.length || 0);
        } else {
          setLogs([]); setTotalCount(0);
        }

        if (statsRes.ok) {
          setTenderStats(await statsRes.json());
        }
        setLoadingLogs(false);
        return;
      }

      // Cas B : Filtrage par Document ID
      if (searchDocumentId.trim()) {
        const res = await fetchWithAuth(`/api/rag/document/${searchDocumentId.trim()}`);
        if (res.ok) {
          const data = await res.json();
          setLogs(data || []);
          setTotalCount(data.length || 0);
        } else {
          setLogs([]); setTotalCount(0);
        }
        setLoadingLogs(false);
        return;
      }

      // Cas C : Pagination et filtrage classique sur /api/rag/
      let url = `/api/rag/?skip=${skip}&limit=${limit}`;
      if (levelFilter) url += `&level=${levelFilter}`;
      if (stageFilter) url += `&stage=${stageFilter}`;

      const res = await fetchWithAuth(url);
      if (res.ok) {
        const data = await res.json();
        setLogs(data.data || []);
        setTotalCount(data.total_count || 0);
      }
    } catch (err) {
      console.error("Erreur Fetch Logs :", err);
    } finally {
      setLoadingLogs(false);
    }
  }, [fetchWithAuth, skip, levelFilter, stageFilter, searchTenderId, searchDocumentId]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleLevelChange = (lvl) => {
    setLevelFilter(lvl);
    setSkip(0);
  };

  // 3. GET /api/rag/{rag_id} (Inspection dynamique du payload à la demande)
  const handleViewDetails = async (logId) => {
    setLoadingDetails(true);
    try {
      const res = await fetchWithAuth(`/api/rag/${logId}`);
      if (res.ok) {
        setSelectedLog(await res.json());
      }
    } catch (err) {
      console.error("Erreur GET /api/rag/{id} :", err);
    } finally {
      setLoadingDetails(false);
    }
  };

  // Basculer le filtre directement sur un Document UUID depuis la modale
  const handleFilterByDocument = (docId) => {
    setSearchTenderId('');
    setSearchDocumentId(docId);
    setSelectedLog(null);
    setSkip(0);
  };

  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.ceil(totalCount / limit) || 1;

  const renderLevelBadge = (level) => {
    switch (level?.toUpperCase()) {
      case 'ERROR':
      case 'CRITICAL':
        return <span className="px-2 py-0.5 rounded text-label-xs font-data-mono bg-error-container text-on-error-container font-semibold">ERROR</span>;
      case 'WARNING':
        return <span className="px-2 py-0.5 rounded text-label-xs font-data-mono bg-tertiary-container text-on-tertiary-container font-semibold">WARNING</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-label-xs font-data-mono bg-secondary-container text-on-secondary-container font-semibold">INFO</span>;
    }
  };

  return (
    <div className="flex flex-col w-full p-6 gap-6 bg-transparent text-on-surface">
      
      {/* EN-TÊTE */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="font-headline-lg text-2xl font-bold">Journaux du Pipeline RAG</h1>
          <p className="text-body-sm text-on-surface-variant">
            Suivi des étapes d'indexation, vectorisation, retrieval et génération LLM.
          </p>
        </div>
        <button
          onClick={() => { fetchStats(); fetchLogs(); }}
          className="flex items-center gap-2 bg-primary text-on-primary px-4 py-2 rounded-xl text-body-sm font-semibold hover:opacity-90 transition-all cursor-pointer shadow-sm"
        >
          <span className="material-symbols-outlined text-[18px]">refresh</span>
          Actualiser
        </button>
      </div>

      {/* 1. STATISTIQUES GLOBALES (affichées par défaut) */}
      {!tenderStats && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          <div className="bg-surface-container rounded-xl p-4 shadow-sm border border-outline/10">
            <div className="flex justify-between items-center mb-2">
              <span className="text-body-sm font-semibold text-on-surface-variant">Total Événements</span>
              <span className="material-symbols-outlined text-primary text-[20px]">database</span>
            </div>
            <div className="font-data-mono text-2xl font-bold">{loadingStats ? '--' : stats?.total_logs ?? 0}</div>
          </div>

          <div className="bg-surface-container rounded-xl p-4 shadow-sm border border-outline/10">
            <div className="flex justify-between items-center mb-2">
              <span className="text-body-sm font-semibold text-error">Erreurs RAG</span>
              <span className="material-symbols-outlined text-error text-[20px]">warning</span>
            </div>
            <div className="font-data-mono text-2xl font-bold text-error">{loadingStats ? '--' : stats?.error_count ?? 0}</div>
          </div>

          <div className="bg-surface-container rounded-xl p-4 shadow-sm border border-outline/10">
            <div className="flex justify-between items-center mb-2">
              <span className="text-body-sm font-semibold text-tertiary">Avertissements</span>
              <span className="material-symbols-outlined text-tertiary text-[20px]">report_problem</span>
            </div>
            <div className="font-data-mono text-2xl font-bold text-tertiary">{loadingStats ? '--' : stats?.warning_count ?? 0}</div>
          </div>

          <div className="bg-surface-container rounded-xl p-4 shadow-sm border border-outline/10">
            <div className="flex justify-between items-center mb-2">
              <span className="text-body-sm font-semibold text-secondary">Durée Moyenne</span>
              <span className="material-symbols-outlined text-secondary text-[20px]">timer</span>
            </div>
            <div className="font-data-mono text-2xl font-bold text-secondary">
              {loadingStats ? '--' : formatDuration(stats?.avg_duration_sec)}
            </div>
          </div>
        </div>
      )}

      {/* 1.1 STATISTIQUES SPÉCIFIQUES AU TENDER (s'affiche uniquement si un Tender ID est recherché) */}
      {tenderStats && (
        <div className="bg-primary-container text-on-primary-container p-4 rounded-xl border border-primary/20 shadow-sm">
          <div className="flex justify-between items-center mb-3">
            <h2 className="font-bold text-lg flex items-center gap-2">
              <span className="material-symbols-outlined">analytics</span>
              Analyse RAG du Tender
            </h2>
            <span className="text-label-xs font-data-mono bg-primary text-on-primary px-2 py-1 rounded">
              Status: {tenderStats.status}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="block opacity-70">Documents traités</span>
              <span className="font-data-mono font-bold">{tenderStats.documents?.completed} / {tenderStats.documents?.total}</span>
            </div>
            <div>
              <span className="block opacity-70">Chunks (Vecteurs)</span>
              <span className="font-data-mono font-bold">{tenderStats.indexing?.total_chunks}</span>
            </div>
            <div>
              <span className="block opacity-70">Moyenne Indexation</span>
              <span className="font-data-mono font-bold">{formatDuration(tenderStats.indexing?.average_duration_sec)}</span>
            </div>
            <div>
              <span className="block opacity-70">Moyenne Génération</span>
              <span className="font-data-mono font-bold">{formatDuration(tenderStats.generation?.average_duration_sec)}</span>
            </div>
          </div>
        </div>
      )}

      {/* 2. RECHERCHE ET FILTRES */}
      <div className="flex flex-col xl:flex-row gap-4 justify-between items-stretch xl:items-center bg-surface-container-low p-3 rounded-xl border border-outline/10">
        
        {/* Filtres par niveau */}
        <div className="flex items-center gap-2">
          <span className="text-label-xs font-semibold text-on-surface-variant">Niveau :</span>
          {[
            { id: '', label: 'Tous' },
            { id: 'INFO', label: 'INFO' },
            { id: 'WARNING', label: 'WARN' },
            { id: 'ERROR', label: 'ERROR' }
          ].map((lvl) => (
            <button
              key={lvl.id}
              onClick={() => handleLevelChange(lvl.id)}
              className={`px-3 py-1 rounded-lg text-label-xs font-semibold transition-all cursor-pointer ${
                levelFilter === lvl.id ? 'bg-primary text-on-primary shadow-sm' : 'bg-surface hover:bg-surface-container-high'
              }`}
            >
              {lvl.label}
            </button>
          ))}
        </div>

        {/* Filtre par étape (stage) */}
        <div className="flex items-center gap-2">
          <span className="text-label-xs font-semibold text-on-surface-variant">Étape :</span>
          <input
            type="text"
            placeholder="ex: retrieval..."
            value={stageFilter}
            onChange={(e) => { setStageFilter(e.target.value); setSkip(0); }}
            className="bg-surface border border-outline/20 px-3 py-1 rounded-lg text-label-xs font-data-mono focus:outline-none focus:border-primary w-32"
          />
        </div>

        {/* Formulaire de recherche combiné Tender ID / Document ID */}
        <form onSubmit={(e) => { e.preventDefault(); setSkip(0); fetchLogs(); }} className="flex gap-2 flex-wrap items-center">
          <input
            type="text"
            placeholder="Tender UUID..."
            value={searchTenderId}
            onChange={(e) => { setSearchTenderId(e.target.value); setSearchDocumentId(''); }}
            className="bg-surface border border-outline/20 px-3 py-1 rounded-lg text-label-xs font-data-mono w-36 focus:outline-none focus:border-primary"
          />
          <span className="text-on-surface-variant text-label-xs font-semibold">ou</span>
          <input
            type="text"
            placeholder="Document UUID..."
            value={searchDocumentId}
            onChange={(e) => { setSearchDocumentId(e.target.value); setSearchTenderId(''); }}
            className="bg-surface border border-outline/20 px-3 py-1 rounded-lg text-label-xs font-data-mono w-36 focus:outline-none focus:border-primary"
          />
          <button type="submit" className="bg-surface-container-high hover:bg-primary hover:text-on-primary px-3 py-1 rounded-lg text-label-xs font-semibold transition-colors cursor-pointer">
            Rechercher
          </button>
        </form>
      </div>

      {/* 3. TABLEAU DES LOGS RAG */}
      <div className="bg-surface rounded-xl border border-outline/10 overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container-low text-label-xs uppercase text-on-surface-variant border-b border-outline/10">
                <th className="p-3">Horodatage</th>
                <th className="p-3">Niveau</th>
                <th className="p-3">Étape / Événement</th>
                <th className="p-3">Message</th>
                <th className="p-3 text-right">Durée / Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline/5 text-body-sm font-data-mono">
              {loadingLogs ? (
                <tr>
                  <td colSpan="5" className="p-6 text-center text-on-surface-variant">Chargement des logs RAG...</td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan="5" className="p-6 text-center text-on-surface-variant">Aucun journal trouvé.</td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-surface-container/50 transition-colors">
                    <td className="p-3 whitespace-nowrap text-label-xs">
                      <div className="font-semibold text-on-surface">
                        {new Date(log.created_at).toLocaleDateString()}
                      </div>
                      <div className="text-on-surface-variant text-[11px]">
                        {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </div>
                    </td>
                    <td className="p-3">{renderLevelBadge(log.level)}</td>
                    <td className="p-3 text-label-xs">
                      <div className="font-bold text-primary">{log.stage || 'N/A'}</div>
                      <div className="text-on-surface-variant">{log.event || '--'}</div>
                    </td>
                    <td className="p-3 text-label-xs max-w-md truncate" title={log.message}>
                      {log.message}
                    </td>
                    <td className="p-3 text-label-xs text-right">
                      <div className="flex items-center justify-end gap-3">
                        <span className="text-on-surface-variant font-semibold">
                          {formatDuration(log.duration_sec)}
                        </span>
                        {/* Clic sur le bouton : Appel direct de GET /api/rag/{id} */}
                        <button
                          onClick={() => handleViewDetails(log.id)}
                          className="p-1.5 rounded-lg bg-primary text-on-primary hover:opacity-90 transition-opacity cursor-pointer flex items-center justify-center"
                          title="Inspecter le payload JSON"
                        >
                          {loadingDetails && selectedLog?.id === log.id ? (
                            <span className="material-symbols-outlined text-[18px] animate-spin">sync</span>
                          ) : (
                            <span className="material-symbols-outlined text-[18px]">code</span>
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* PAGINATION (Masquée en mode filtrage spécifique UUID) */}
        {!searchTenderId && !searchDocumentId && (
          <div className="flex justify-between items-center p-3 bg-surface-container-low border-t border-outline/10 text-label-xs font-data-mono">
            <span>
              Affichage de {logs.length > 0 ? skip + 1 : 0} à {Math.min(skip + limit, totalCount)} sur {totalCount} logs
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setSkip(Math.max(0, skip - limit))}
                disabled={skip === 0}
                className="px-3 py-1.5 rounded bg-surface border border-outline/10 disabled:opacity-40 cursor-pointer hover:bg-surface-container-high"
              >
                Précédent
              </button>
              <span className="flex items-center px-2">Page {currentPage} / {totalPages}</span>
              <button
                onClick={() => setSkip(skip + limit)}
                disabled={skip + limit >= totalCount}
                className="px-3 py-1.5 rounded bg-surface border border-outline/10 disabled:opacity-40 cursor-pointer hover:bg-surface-container-high"
              >
                Suivant
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 4. MODALE D'INSPECTION DÉTAILLÉE DU LOG (Générée par /{rag_id}) */}
      {selectedLog && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-surface-container-high rounded-2xl max-w-3xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto shadow-2xl border border-outline/20">
            
            <div className="flex justify-between items-start border-b border-outline/10 pb-3">
              <div>
                <h3 className="font-headline-sm font-bold text-lg">Inspection RAG Event</h3>
                <p className="text-label-xs font-data-mono text-on-surface-variant">Log ID: {selectedLog.id}</p>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="p-1 rounded-lg hover:bg-surface-container-highest cursor-pointer"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            {/* Metadonnées d'exécution */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-label-xs font-data-mono">
              <div className="bg-surface p-2 rounded border border-outline/10">
                <span className="text-on-surface-variant block">Étape (Stage)</span>
                <span className="font-bold text-primary">{selectedLog.stage || 'N/A'}</span>
              </div>
              <div className="bg-surface p-2 rounded border border-outline/10">
                <span className="text-on-surface-variant block">Événement</span>
                <span className="font-bold">{selectedLog.event || 'N/A'}</span>
              </div>
              <div className="bg-surface p-2 rounded border border-outline/10">
                <span className="text-on-surface-variant block">Durée Exec</span>
                <span className="font-bold">{formatDuration(selectedLog.duration_sec)}</span>
              </div>
              <div className="bg-surface p-2 rounded border border-outline/10">
                <span className="text-on-surface-variant block">Niveau</span>
                <div>{renderLevelBadge(selectedLog.level)}</div>
              </div>
            </div>

            {/* Message principal */}
            <div className="bg-surface p-3 rounded-xl border border-outline/10 font-data-mono text-body-sm">
              <span className="text-label-xs text-on-surface-variant font-bold block mb-1">Message d'exécution :</span>
              <p className="whitespace-pre-wrap">{selectedLog.message}</p>
            </div>

            {/* Clés Étrangères liées */}
            <div className="grid grid-cols-2 gap-2 text-label-xs font-data-mono">
              <div className="bg-surface p-2 rounded border border-outline/10">
                <span className="text-on-surface-variant block">Tender ID</span>
                <span className="truncate block">{selectedLog.tender_id || 'Aucun'}</span>
              </div>
              <div className="bg-surface p-2 rounded border border-outline/10">
                <span className="text-on-surface-variant block">Document ID</span>
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate block">{selectedLog.document_id || 'Aucun'}</span>
                  {selectedLog.document_id && (
                    <button 
                      onClick={() => handleFilterByDocument(selectedLog.document_id)}
                      className="text-primary hover:underline text-[10px] cursor-pointer whitespace-nowrap"
                    >
                      Filtrer logs
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Inspecteur du JSONB Details */}
            <div className="bg-surface-container-lowest p-4 rounded-xl border border-outline/10 font-data-mono">
              <span className="text-label-xs text-on-surface-variant font-bold block mb-2">Payload Détails (JSONB) :</span>
              {selectedLog.details ? (
                <pre className="text-[12px] text-primary overflow-x-auto p-3 bg-surface rounded-lg max-h-60 border border-outline/10">
                  {JSON.stringify(selectedLog.details, null, 2)}
                </pre>
              ) : (
                <span className="text-label-xs text-on-surface-variant italic">Aucun détail supplémentaire enregistré dans ce log.</span>
              )}
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedLog(null)}
                className="bg-primary text-on-primary px-4 py-2 rounded-xl text-body-sm font-semibold cursor-pointer hover:opacity-90 transition-opacity"
              >
                Fermer
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}