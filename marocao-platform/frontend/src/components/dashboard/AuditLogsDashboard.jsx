import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function AuditLogsDashboard() {
  const { fetchWithAuth } = useAuth();

  // États pour les données
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [latestLogs, setLatestLogs] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedLog, setSelectedLog] = useState(null);

  // Mode de vue : 'all' (liste / recherche) ou 'latest' (derniers du jour)
  const [viewMode, setViewMode] = useState('all');

  // États de filtrage & recherche
  const [statusFilter, setStatusFilter] = useState('');
  const [documentSearchId, setDocumentSearchId] = useState('');
  const [skip, setSkip] = useState(0);
  const limit = 15;

  // États de chargement
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // 1. GET /api/audit-logs/stats
  const fetchStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      const res = await fetchWithAuth('/api/audit-logs/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.error("Erreur GET /audit-logs/stats :", err);
    } finally {
      setLoadingStats(false);
    }
  }, [fetchWithAuth]);

  // 2. GET /api/audit-logs/latest
  const fetchLatestLogs = useCallback(async () => {
    setLoadingLogs(true);
    try {
      const res = await fetchWithAuth('/api/audit-logs/latest?limit=10&today_only=true');
      if (res.ok) {
        const data = await res.json();
        setLatestLogs(data || []);
      }
    } catch (err) {
      console.error("Erreur GET /audit-logs/latest :", err);
    } finally {
      setLoadingLogs(false);
    }
  }, [fetchWithAuth]);

  // 3. GET /api/audit-logs/document/{document_id} OU POST /api/audit-logs/search / GET /api/audit-logs/
  const fetchLogs = useCallback(async () => {
    if (viewMode === 'latest') {
      fetchLatestLogs();
      return;
    }

    setLoadingLogs(true);
    try {
      // Cas : Recherche par Document ID spécifique
      if (documentSearchId.trim()) {
        const res = await fetchWithAuth(`/api/audit-logs/document/${documentSearchId.trim()}`);
        if (res.ok) {
          const data = await res.json();
          setLogs(data || []);
          setTotalCount(data.length || 0);
        } else {
          setLogs([]);
          setTotalCount(0);
        }
        setLoadingLogs(false);
        return;
      }

      // Cas : Recherche via POST /api/audit-logs/search
      if (statusFilter) {
        const res = await fetchWithAuth('/api/audit-logs/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            validation_status: statusFilter,
            skip: skip,
            limit: limit
          })
        });
        if (res.ok) {
          const data = await res.json();
          setLogs(data.data || []);
          setTotalCount(data.total_count || 0);
        }
      } else {
        // Cas par défaut : GET /api/audit-logs/
        const res = await fetchWithAuth(`/api/audit-logs/?skip=${skip}&limit=${limit}`);
        if (res.ok) {
          const data = await res.json();
          setLogs(data.data || []);
          setTotalCount(data.total_count || 0);
        }
      }
    } catch (err) {
      console.error("Erreur récupération logs :", err);
    } finally {
      setLoadingLogs(false);
    }
  }, [fetchWithAuth, skip, statusFilter, documentSearchId, viewMode, fetchLatestLogs]);

  // 4. GET /api/audit-logs/{audit_id} (Chargement du log spécifique pour la modale)
  const handleOpenDetail = async (auditId) => {
    setLoadingDetail(true);
    try {
      const res = await fetchWithAuth(`/api/audit-logs/${auditId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedLog(data);
      }
    } catch (err) {
      console.error("Erreur GET /audit-logs/{audit_id} :", err);
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleStatusFilterChange = (newStatus) => {
    setStatusFilter(newStatus);
    setSkip(0);
  };

  const handleDocumentSearchSubmit = (e) => {
    e.preventDefault();
    setSkip(0);
    fetchLogs();
  };

  const activeLogsList = viewMode === 'latest' ? latestLogs : logs;
  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.ceil(totalCount / limit) || 1;

  const renderStatusBadge = (status) => {
  switch (status) {
    case 'VALIDATED':
      return (
        <span className="text-label-xs font-data-mono text-emerald-500 font-bold">
          Validé
        </span>
      );
    case 'CORRECTED':
      return (
        <span className="text-label-xs font-data-mono text-error font-bold">
          Corrigé
        </span>
      );
    default: // PENDING
      return (
        <span className="text-label-xs font-data-mono text-amber-500 font-bold">
          En attente
        </span>
      );
  }
};

  return (
    <div className="flex flex-col w-full gap-6 text-on-surface">
      
      {/* EN-TÊTE */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="font-headline-lg text-2xl font-bold">Journaux d'Audit IA & Classification</h1>
          <p className="text-body-sm text-on-surface-variant">
            Traçabilité des décisions LLM, performances d'extraction et validations.
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

      {/* 1. KPI STATS (/api/audit-logs/stats) */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
        <div className="bg-surface-container rounded-xl p-4 shadow-sm border border-outline/10">
          <div className="flex justify-between items-center mb-2">
            <span className="text-body-sm font-semibold text-on-surface-variant">Total Inférences</span>
            <span className="material-symbols-outlined text-primary text-[20px]">assignment</span>
          </div>
          <div className="font-data-mono text-2xl font-bold">{loadingStats ? '--' : stats?.total_logs ?? 0}</div>
        </div>

        {/* Pending */}
        <div className="bg-surface-container rounded-xl p-4 shadow-sm border border-outline/10">
        <div className="flex justify-between items-center mb-2">
            <span className="text-body-sm font-semibold text-amber-500">En Attente</span>
            <span className="material-symbols-outlined text-amber-500 text-[20px]">hourglass_empty</span>
        </div>
        <div className="font-data-mono text-2xl font-bold text-amber-500">
            {loadingStats ? '--' : stats?.pending_count ?? 0}
        </div>
        </div>

        {/* Validated KPI */}
        <div className="bg-surface-container rounded-xl p-4 shadow-sm border border-outline/10">
        <div className="flex justify-between items-center mb-2">
            <span className="text-body-sm font-semibold text-emerald-500">Validés</span>
            <span className="material-symbols-outlined text-emerald-500 text-[20px]">check_circle</span>
        </div>
        <div className="font-data-mono text-2xl font-bold text-emerald-500">
            {loadingStats ? '--' : stats?.validated_count ?? 0}
        </div>
        </div>

        <div className="bg-surface-container rounded-xl p-4 shadow-sm border border-outline/10">
          <div className="flex justify-between items-center mb-2">
            <span className="text-body-sm font-semibold text-error">Corrigés</span>
            <span className="material-symbols-outlined text-error text-[20px]">edit_note</span>
          </div>
          <div className="font-data-mono text-2xl font-bold text-error">{loadingStats ? '--' : stats?.corrected_count ?? 0}</div>
        </div>

        <div className="bg-surface-container rounded-xl p-4 shadow-sm border border-outline/10">
          <div className="flex justify-between items-center mb-2">
            <span className="text-body-sm font-semibold text-tertiary">Précision (Accuracy)</span>
            <span className="material-symbols-outlined text-tertiary text-[20px]">psychology</span>
          </div>
          <div className="font-data-mono text-2xl font-bold text-tertiary">
            {loadingStats ? '--' : (stats?.accuracy_rate_percentage !== null ? `${stats?.accuracy_rate_percentage}%` : 'N/A')}
          </div>
        </div>
      </div>

      {/* 2. MODE DE VUE ET RECHERCHE */}
      <div className="flex flex-col lg:flex-row gap-4 justify-between items-stretch lg:items-center bg-surface-container-low p-3 rounded-xl border border-outline/10">
        
        {/* Switcher d'onglet : Tous les logs vs Récents (Aujourd'hui) */}
        <div className="flex gap-2">
          <button
            onClick={() => { setViewMode('all'); setSkip(0); }}
            className={`px-3 py-1.5 rounded-lg text-body-sm font-semibold transition-all cursor-pointer ${
              viewMode === 'all' ? 'bg-primary text-on-primary shadow-sm' : 'bg-surface hover:bg-surface-container-high'
            }`}
          >
            Tous les logs
          </button>
          <button
            onClick={() => { setViewMode('latest'); }}
            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-body-sm font-semibold transition-all cursor-pointer ${
              viewMode === 'latest' ? 'bg-primary text-on-primary shadow-sm' : 'bg-surface hover:bg-surface-container-high'
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">today</span>
            Derniers du jour
          </button>
        </div>

        {/* Filtrage par Statut (Si vue 'all') */}
        {viewMode === 'all' && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-label-xs font-semibold text-on-surface-variant">Statut:</span>
            {[
              { id: '', label: 'Tous' },
              { id: 'PENDING', label: 'PENDING' },
              { id: 'VALIDATED', label: 'VALIDATED' },
              { id: 'CORRECTED', label: 'CORRECTED' }
            ].map((st) => (
              <button
                key={st.id}
                onClick={() => handleStatusFilterChange(st.id)}
                className={`px-2.5 py-1 rounded text-label-xs font-semibold transition-all cursor-pointer ${
                  statusFilter === st.id ? 'bg-secondary text-on-secondary' : 'bg-surface hover:bg-surface-container-high'
                }`}
              >
                {st.label}
              </button>
            ))}
          </div>
        )}

        {/* Recherche par Document ID (/document/{document_id}) */}
        {viewMode === 'all' && (
          <form onSubmit={handleDocumentSearchSubmit} className="flex gap-2">
            <input
              type="text"
              placeholder="Recherche Document UUID..."
              value={documentSearchId}
              onChange={(e) => setDocumentSearchId(e.target.value)}
              className="bg-surface border border-outline/20 px-3 py-1.5 rounded-lg text-label-xs font-data-mono w-64 focus:outline-none focus:border-primary"
            />
            <button type="submit" className="bg-surface-container-high hover:bg-primary hover:text-on-primary px-3 py-1.5 rounded-lg text-label-xs font-semibold transition-colors cursor-pointer">
              Chercher
            </button>
          </form>
        )}
      </div>

      {/* 3. TABLEAU DES LOGS */}
      <div className="bg-surface rounded-xl border border-outline/10 overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container-low text-label-xs uppercase text-on-surface-variant border-b border-outline/10">
                <th className="p-3">Horodatage</th>
                <th className="p-3">Type Prédit</th>
                <th className="p-3">Confiance</th>
                <th className="p-3">Modèle / Durée</th>
                <th className="p-3">Tokens (P / G)</th>
                <th className="p-3">Scan / Langue</th>
                <th className="p-3 text-center" colSpan="2">Statut</th>
                {/* <th className="p-3 text-right">Actions</th> */}
              </tr>
            </thead>
            <tbody className="divide-y divide-outline/5 text-body-sm font-data-mono">
              {loadingLogs ? (
                <tr>
                  <td colSpan="8" className="p-6 text-center text-on-surface-variant">Chargement des données...</td>
                </tr>
              ) : activeLogsList.length === 0 ? (
                <tr>
                  <td colSpan="8" className="p-6 text-center text-on-surface-variant">Aucun log d'audit trouvé.</td>
                </tr>
              ) : (
                activeLogsList.map((log) => (
                  <tr key={log.id} className="hover:bg-surface-container/50 transition-colors">
                    <td className="p-3 whitespace-nowrap text-label-xs">
                        <div className="font-semibold text-on-surface">
                            {new Date(log.created_at).toLocaleDateString()}
                        </div>
                        <div className="text-on-surface-variant">
                            {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </div>
                    </td>
                    <td className="p-3 font-bold text-primary">
                      {log.predicted_type}
                      {log.corrected_type && (
                        <span className="block text-error text-label-xs font-normal">
                          → {log.corrected_type}
                        </span>
                      )}
                    </td>
                    <td className="p-3">
                      <span className={`font-bold ${log.confidence_score >= 80 ? 'text-secondary' : 'text-warning'}`}>
                        {log.confidence_score ?? 0}%
                      </span>
                    </td>
                    <td className="p-3 text-label-xs">
                      <div>{log.model_used}</div>
                      <div className="text-on-surface-variant">{log.execution_duration_sec ? `${log.execution_duration_sec.toFixed(2)}s` : '--'}</div>
                    </td>
                    <td className="p-3 text-label-xs text-on-surface-variant">
                      {log.prompt_tokens ?? 0} / {log.generated_tokens ?? 0}
                    </td>
                    <td className="p-3 text-label-xs">
                      <div className="uppercase">{log.detected_language || 'N/A'}</div>
                      <div className="text-on-surface-variant">{log.is_scanned ? 'OCR (Scan)' : 'Texte natif'}</div>
                    </td>
                    <td className="p-3">
                      {renderStatusBadge(log.validation_status)}
                    </td>
                    <td className="p-3 text-center">
                    <button
                        onClick={() => handleOpenDetail(log.id)}
                        className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer p-1"
                        title="Voir les détails complets"
                    >
                        <span className="material-symbols-outlined text-[20px] block">visibility</span>
                    </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* PAGINATION (Visible uniquement en mode 'all') */}
        {viewMode === 'all' && !documentSearchId && (
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

      {/* 4. MODALE DE DÉTAILS DU LOG (`GET /api/audit-logs/{audit_id}`) */}
      {selectedLog && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-surface-container-high rounded-2xl max-w-2xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto shadow-2xl border border-outline/20">
            
            <div className="flex justify-between items-start border-b border-outline/10 pb-3">
              <div>
                <h3 className="font-headline-sm font-bold text-lg">Détails de l'Audit Log</h3>
                <p className="text-label-xs font-data-mono text-on-surface-variant">Audit ID: {selectedLog.id}</p>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="p-1 rounded-lg hover:bg-surface-container-highest cursor-pointer"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            {loadingDetail ? (
              <div className="p-8 text-center font-data-mono text-body-sm">Chargement des détails de l'audit...</div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3 text-body-sm font-data-mono">
                  <div className="bg-surface p-3 rounded-lg border border-outline/10">
                    <span className="text-label-xs text-on-surface-variant block">Document ID</span>
                    <span className="truncate block text-primary">{selectedLog.document_id}</span>
                  </div>
                  <div className="bg-surface p-3 rounded-lg border border-outline/10">
                    <span className="text-label-xs text-on-surface-variant block">Statut de Validation</span>
                    <div className="mt-1">{renderStatusBadge(selectedLog.validation_status)}</div>
                  </div>
                </div>

                <div className="bg-surface p-4 rounded-xl border border-outline/10 space-y-2 font-data-mono">
                  <h4 className="font-bold text-body-sm text-on-surface-variant border-b border-outline/10 pb-1">Résultats de la Classification</h4>
                  <div className="grid grid-cols-2 gap-2 text-body-sm">
                    <div>Type Prédit : <span className="font-bold text-primary">{selectedLog.predicted_type}</span></div>
                    <div>Confiance : <span className="font-bold">{selectedLog.confidence_score}%</span></div>
                    {selectedLog.corrected_type && (
                      <div className="col-span-2 text-error">Type Corrigé : <span className="font-bold">{selectedLog.corrected_type}</span></div>
                    )}
                  </div>
                  {selectedLog.classification_reason && (
                    <div className="mt-2 text-label-xs bg-surface-container-low p-2 rounded">
                      <span className="text-on-surface-variant font-bold block">Raisonnement :</span>
                      {selectedLog.classification_reason}
                    </div>
                  )}
                </div>

                <div className="bg-surface p-4 rounded-xl border border-outline/10 space-y-2 font-data-mono text-label-xs">
                  <h4 className="font-bold text-body-sm text-on-surface-variant border-b border-outline/10 pb-1">Performances LLM</h4>
                  <div className="grid grid-cols-2 gap-2">
                    <div>Modèle : <span className="font-bold">{selectedLog.model_used}</span></div>
                    <div>Durée Exec : <span className="font-bold">{selectedLog.execution_duration_sec}s</span></div>
                    <div>Durée Ollama : <span className="font-bold">{selectedLog.ollama_total_duration ?? 'N/A'}s</span></div>
                    <div>Tokens (Prompt / Gen) : <span className="font-bold">{selectedLog.prompt_tokens} / {selectedLog.generated_tokens}</span></div>
                  </div>
                </div>

                <div className="bg-surface p-4 rounded-xl border border-outline/10 space-y-2 font-data-mono text-label-xs">
                  <h4 className="font-bold text-body-sm text-on-surface-variant border-b border-outline/10 pb-1">Analyse Documentaire</h4>
                  <div className="grid grid-cols-2 gap-2">
                    <div>Caractères : <span className="font-bold">{selectedLog.text_length_chars ?? 0}</span></div>
                    <div>Mots : <span className="font-bold">{selectedLog.text_word_count ?? 0}</span></div>
                    <div>Mode Scanné (OCR) : <span className="font-bold">{selectedLog.is_scanned ? 'Oui' : 'Non'}</span></div>
                    <div>Inspection : <span className="font-bold">{selectedLog.inspection_method || 'N/A'}</span></div>
                  </div>

                  {selectedLog.extracted_keywords?.length > 0 && (
                    <div className="mt-2">
                      <span className="text-on-surface-variant font-bold block mb-1">Mots-clés extraits :</span>
                      <div className="flex flex-wrap gap-1">
                        {selectedLog.extracted_keywords.map((kw, idx) => (
                          <span key={idx} className="bg-primary/10 text-primary px-2 py-0.5 rounded text-[11px]">
                            {kw}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}

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