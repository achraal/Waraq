import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function DocumentClassifier() {
  const { fetchWithAuth } = useAuth();
  
  // États des données globales
  const [metrics, setMetrics] = useState(null);
  const [globalStats, setGlobalStats] = useState(null);
  const [latestDocs, setLatestDocs] = useState([]);
  const [reasonStats, setReasonStats] = useState([]);
  
  // États pour la liste complète des documents
  const [allDocs, setAllDocs] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [docsPerPage, setDocsPerPage] = useState(10); 
  
  const [loading, setLoading] = useState(true);

  // États pour les Modals (Édition et Détails)
  const [selectedDocForEdit, setSelectedDocForEdit] = useState(null);
  const [editFormData, setEditFormData] = useState({ file_type: '', is_classified: false });
  const [selectedDocForDetails, setSelectedDocForDetails] = useState(null);

  // Chargement de toutes les données du Dashboard
  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [resMetrics, resStats, resLatest, resReasons, resAllDocs] = await Promise.all([
        fetchWithAuth('/api/classifier/metrics/stats'),
        fetchWithAuth('/api/classifier/stats'),
        fetchWithAuth('/api/classifier/documents/latest-classified?limit=5'),
        fetchWithAuth('/api/classifier/documents/stats/classification-reasons'),
        fetchWithAuth('/api/classifier/documents')
      ]);

      if (resMetrics.ok) setMetrics(await resMetrics.json());
      if (resStats.ok) setGlobalStats(await resStats.json());
      if (resLatest.ok) {
        const d = await resLatest.json();
        setLatestDocs(d.documents || []);
      }
      if (resReasons.ok) {
        const d = await resReasons.json();
        setReasonStats(d.by_reason || []);
      }
      if (resAllDocs.ok) {
        const d = await resAllDocs.json();
        setAllDocs(d.items || []);
      }
    } catch (err) {
      console.error("Erreur chargement dashboard:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  // --- ACTIONS MODAL ÉDITION ---
  const handleOpenEditModal = async (docId) => {
    try {
      const res = await fetchWithAuth(`/api/classifier/documents/${docId}`);
      if (res.ok) {
        const doc = await res.json();
        setSelectedDocForEdit(doc);
        setEditFormData({ file_type: doc.file_type || '', is_classified: doc.is_classified });
      }
    } catch (err) {
      alert("Erreur lors de la récupération du document pour édition.");
    }
  };

  const handleSaveEdit = async () => {
    try {
      const res = await fetchWithAuth(`/api/classifier/documents/${selectedDocForEdit.id}`, {
        method: 'PATCH',
        body: JSON.stringify(editFormData)
      });
      if (res.ok) {
        setSelectedDocForEdit(null);
        loadDashboardData(); 
      } else {
        alert("Erreur lors de la mise à jour.");
      }
    } catch (err) {
      console.error(err);
    }
  };

  // --- ACTIONS MODAL DÉTAILS ---
  const handleOpenDetailsModal = async (docId) => {
    try {
      const res = await fetchWithAuth(`/api/classifier/documents/${docId}`);
      if (res.ok) {
        const doc = await res.json();
        setSelectedDocForDetails(doc);
      }
    } catch (err) {
      alert("Erreur lors de la récupération des détails du document.");
    }
  };

  const renderBool = (value) => {
    return value 
      ? <span className="text-green-500 font-bold">Oui</span>
      : <span className="text-red-500 font-bold">Non</span>;
  };

  // --- LOGIQUE PAGINATION ---
  const indexOfLastDoc = currentPage * docsPerPage;
  const indexOfFirstDoc = indexOfLastDoc - docsPerPage;
  const currentDocs = allDocs.slice(indexOfFirstDoc, indexOfLastDoc);
  const totalPages = Math.ceil(allDocs.length / docsPerPage);

  if (loading) return <div className="p-10 text-center">Chargement du Dashboard IA...</div>;

  return (
    <div className="p-6 max-w-7xl mx-auto flex flex-col gap-6">
      
      {/* HEADER */}
      <div>
        <h1 className="text-3xl font-bold text-on-surface">Dashboard Intelligence Documentaire</h1>
        <p className="text-sm text-on-surface-variant mt-1">Supervision globale des classifications et des performances de l'IA.</p>
      </div>

      {metrics && (
        <>
          {/* 1. MÉTRIQUES GLOBALES */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-surface-container-lowest p-6 rounded-2xl border border-outline-variant/30 shadow-sm flex flex-col items-center">
              <span className="material-symbols-outlined text-4xl text-secondary mb-2">radar</span>
              <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">Précision IA</span>
              <span className="text-4xl font-black mt-2 text-on-surface">{metrics.accuracy_metrics.accuracy_rate_percentage}%</span>
              <span className="text-xs text-on-surface-variant mt-1">Sur {metrics.accuracy_metrics.total_reviewed_by_human} validations</span>
            </div>
            <div className="bg-surface-container-lowest p-6 rounded-2xl border border-outline-variant/30 shadow-sm flex flex-col items-center">
              <span className="material-symbols-outlined text-4xl text-primary mb-2">inventory_2</span>
              <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">Couverture globale</span>
              <span className="text-4xl font-black mt-2 text-on-surface">{metrics.overview.classification_coverage_percentage}%</span>
              <span className="text-xs text-on-surface-variant mt-1">{metrics.overview.classified_documents} classés / {metrics.overview.total_documents} total</span>
            </div>
            <div className="bg-surface-container-lowest p-6 rounded-2xl border border-outline-variant/30 shadow-sm flex flex-col items-center">
              <span className="material-symbols-outlined text-4xl text-tertiary mb-2">bolt</span>
              <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">Temps Moyen (OCR+LLM)</span>
              <span className="text-4xl font-black mt-2 text-on-surface">{metrics.overview.avg_response_time_seconds}s</span>
              <span className="text-xs text-on-surface-variant mt-1">Par document traité</span>
            </div>
          </div>

          {/* 1.5. NOUVEAU : STATISTIQUES DE VALIDATION HUMAINE */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/30 flex items-center justify-between shadow-sm">
               <div>
                  <span className="text-[10px] uppercase font-bold text-on-surface-variant tracking-wider">En attente de validation</span>
                  <div className="text-2xl font-black text-on-surface mt-1">{metrics.human_validation.pending_validation}</div>
               </div>
               <span className="material-symbols-outlined text-on-surface-variant/50 text-4xl">pending_actions</span>
            </div>
            <div className="bg-green-500/10 p-4 rounded-xl border border-green-500/20 flex items-center justify-between shadow-sm">
               <div>
                  <span className="text-[10px] uppercase font-bold text-green-600 tracking-wider">Validés (Conformes)</span>
                  <div className="text-2xl font-black text-green-600 mt-1">{metrics.human_validation.total_validated}</div>
               </div>
               <span className="material-symbols-outlined text-green-500/50 text-4xl">task_alt</span>
            </div>
            <div className="bg-orange-500/10 p-4 rounded-xl border border-orange-500/20 flex items-center justify-between shadow-sm">
               <div>
                  <span className="text-[10px] uppercase font-bold text-orange-600 tracking-wider">Corrigés manuellement</span>
                  <div className="text-2xl font-black text-orange-600 mt-1">{metrics.human_validation.corrected_by_user}</div>
               </div>
               <span className="material-symbols-outlined text-orange-500/50 text-4xl">edit_note</span>
            </div>
          </div>
        </>
      )}

      {/* 2. STATISTIQUES DÉTAILLÉES (Grille de 3 Colonnes maintenant) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Colonne 1 : Derniers Documents */}
        <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/30 shadow-sm overflow-hidden flex flex-col">
          <div className="p-4 border-b border-outline-variant/20 bg-surface-container-low font-bold text-on-surface text-sm">
            Derniers classifiés (Aujourd'hui)
          </div>
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-container-lowest text-[10px] uppercase text-on-surface-variant border-b border-outline-variant/10">
                <tr>
                  <th className="p-3">Fichier</th>
                  <th className="p-3">Type</th>
                  <th className="p-3 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {latestDocs.map(doc => (
                  <tr key={doc.id} className="hover:bg-surface-container-low/30">
                    <td className="p-3 font-mono text-xs max-w-[100px] truncate" title={doc.file_name}>{doc.file_name}</td>
                    <td className="p-3 font-bold text-primary text-xs">{doc.file_type || 'INCONNU'}</td>
                    <td className="p-3 text-center flex justify-center gap-2">
                      <button onClick={() => handleOpenDetailsModal(doc.id)} className="text-tertiary hover:opacity-70"><span className="material-symbols-outlined text-sm">visibility</span></button>
                    </td>
                  </tr>
                ))}
                {latestDocs.length === 0 && (
                  <tr><td colSpan="3" className="p-4 text-center text-xs text-on-surface-variant">Aucun document classifié aujourd'hui.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Colonne 2 : Raisons de classification */}
        <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/30 shadow-sm overflow-hidden flex flex-col">
          <div className="p-4 border-b border-outline-variant/20 bg-surface-container-low font-bold text-on-surface text-sm">
            Répartition par Règles IA
          </div>
          <div className="p-4 flex flex-col gap-2 overflow-y-auto max-h-[250px] flex-1">
            {reasonStats.map((stat, idx) => (
              <div key={idx} className="flex justify-between items-center bg-surface-container-low/50 p-2.5 rounded-lg border border-outline-variant/20">
                <span className="text-xs font-medium text-on-surface truncate pr-2 max-w-[75%]" title={stat.reason}>{stat.reason}</span>
                <span className="bg-primary/10 text-primary px-2.5 py-0.5 rounded-full text-[10px] font-bold border border-primary/20">
                  {stat.count}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Colonne 3 : NOUVEAU - Répartition par Type */}
        <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/30 shadow-sm overflow-hidden flex flex-col">
          <div className="p-4 border-b border-outline-variant/20 bg-surface-container-low font-bold text-on-surface text-sm">
            Répartition par Type de Document
          </div>
          <div className="p-4 flex flex-col gap-2 overflow-y-auto max-h-[250px] flex-1">
            {metrics?.distribution?.by_file_type?.map((stat, idx) => (
              <div key={idx} className="flex justify-between items-center bg-surface-container-low/50 p-2.5 rounded-lg border border-outline-variant/20">
                <span className="text-xs font-bold text-primary truncate pr-2">{stat.file_type || 'INCONNU'}</span>
                <span className="bg-surface-container-highest text-on-surface px-2.5 py-0.5 rounded-full text-[10px] font-bold">
                  {stat.count} docs
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 3. LISTE COMPLÈTE DES DOCUMENTS (Avec Pagination Dynamique) */}
      <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/30 shadow-sm overflow-hidden flex flex-col">
        <div className="p-4 border-b border-outline-variant/20 bg-surface-container-low flex justify-between items-center">
          <span className="font-bold text-on-surface">Base de données globale ({allDocs.length} documents)</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-container-lowest text-xs uppercase text-on-surface-variant">
              <tr>
                <th className="p-4">Fichier</th>
                <th className="p-4">Type</th>
                <th className="p-4 text-center">Statut IA</th>
                <th className="p-4 text-center">RAG</th>
                <th className="p-4 text-center">Validation</th>
                <th className="p-4 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/20">
              {currentDocs.map(doc => (
                <tr key={doc.id} className="hover:bg-surface-container-low/30 transition-colors">
                  <td className="p-4 font-mono text-xs max-w-[250px] truncate" title={doc.file_name}>{doc.file_name}</td>
                  <td className="p-4 font-bold text-primary">{doc.file_type || '-'}</td>
                  <td className="p-4 text-center">
                    {doc.is_classified 
                      ? <span className="bg-primary/10 text-primary px-2 py-1 rounded text-[10px] font-bold border border-primary/20">CLASSIFIÉ</span>
                      : <span className="bg-surface-variant text-on-surface-variant px-2 py-1 rounded text-[10px] border border-outline-variant/30">EN ATTENTE</span>
                    }
                  </td>
                  <td className="p-4 text-center">
                    {renderBool(doc.rag_processed)}
                  </td>
                  <td className="p-4 text-center">
                    {doc.validation_status === 'VALIDATED' && (
                      <span className="bg-green-500/10 text-green-500 border border-green-500/20 px-2 py-1 rounded text-[10px] font-bold">VALIDÉ</span>
                    )}
                    {doc.validation_status === 'CORRECTED' && (
                      <span className="bg-orange-500/10 text-orange-500 border border-orange-500/20 px-2 py-1 rounded text-[10px] font-bold">CORRIGÉ</span>
                    )}
                    {(!doc.validation_status || doc.validation_status === 'PENDING') && (
                      <span className="bg-surface-variant text-on-surface-variant border border-outline-variant/30 px-2 py-1 rounded text-[10px]">EN ATTENTE</span>
                    )}
                  </td>
                  <td className="p-4 text-center flex justify-center gap-3">
                    <button onClick={() => handleOpenDetailsModal(doc.id)} className="text-tertiary hover:opacity-70 transition-opacity" title="Détails complets">
                      <span className="material-symbols-outlined text-lg">visibility</span>
                    </button>
                    <button onClick={() => handleOpenEditModal(doc.id)} className="text-secondary hover:opacity-70 transition-opacity" title="Éditer le document">
                      <span className="material-symbols-outlined text-lg">edit</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {/* Contrôles de Pagination Avancés */}
        <div className="p-4 border-t border-outline-variant/20 flex flex-col md:flex-row justify-between items-center bg-surface-container-lowest gap-4">
          <div className="flex items-center gap-3">
            <span className="text-xs text-on-surface-variant font-medium">Lignes par page :</span>
            <select 
              value={docsPerPage} 
              onChange={(e) => { 
                setDocsPerPage(Number(e.target.value)); 
                setCurrentPage(1); 
              }}
              className="bg-surface-container border border-outline-variant/30 rounded-lg px-2 py-1 text-xs text-on-surface focus:outline-none focus:border-primary cursor-pointer"
            >
              <option value={10}>10</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={500}>500 (Tout afficher)</option>
            </select>
          </div>

          {totalPages > 0 && (
            <div className="flex items-center gap-4">
              <button 
                onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                disabled={currentPage === 1}
                className="px-3 py-1 bg-surface-container hover:bg-surface-container-high rounded text-sm disabled:opacity-50 transition-colors"
              >
                Précédent
              </button>
              <span className="text-xs font-medium text-on-surface-variant">Page {currentPage} sur {totalPages}</span>
              <button 
                onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                disabled={currentPage === totalPages}
                className="px-3 py-1 bg-surface-container hover:bg-surface-container-high rounded text-sm disabled:opacity-50 transition-colors"
              >
                Suivant
              </button>
            </div>
          )}
        </div>
      </div>

      {/* --- MODAL : DÉTAILS COMPLETS DU DOCUMENT --- */}
      {selectedDocForDetails && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-surface-container-lowest p-6 rounded-2xl shadow-xl border border-outline-variant/30 w-full max-w-5xl max-h-[90vh] overflow-y-auto flex flex-col gap-6">
            
            <div className="flex justify-between items-start border-b border-outline-variant/20 pb-4">
              <div>
                <h3 className="text-xl font-bold text-on-surface flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">description</span> 
                  Détails intégraux du Document
                </h3>
              </div>
              <button onClick={() => setSelectedDocForDetails(null)} className="text-on-surface-variant hover:text-error bg-surface-container p-1 rounded-full transition-colors">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
              
              {/* Identifiants et Chemins */}
              <div className="flex flex-col gap-3">
                <h4 className="font-bold text-sm text-primary uppercase border-b border-primary/20 pb-1">Identifiants et Chemins</h4>
                <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">ID Document</span> <span className="font-mono text-xs text-on-surface">{selectedDocForDetails.id}</span></div>
                <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">ID Appel d'Offres (Tender)</span> <span className="font-mono text-xs text-on-surface">{selectedDocForDetails.tender_id}</span></div>
                <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Nom du fichier</span> <span className="break-all font-mono text-xs text-on-surface">{selectedDocForDetails.file_name}</span></div>
                <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Type détecté</span> <span className="font-bold text-on-surface">{selectedDocForDetails.file_type || 'Non spécifié'}</span></div>
                <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Chemin Source</span> <span className="break-all font-mono text-[11px] text-on-surface">{selectedDocForDetails.file_path}</span></div>
                <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Chemin Classifié</span> <span className="break-all font-mono text-[11px] text-on-surface">{selectedDocForDetails.classified_file_path || '-'}</span></div>
              </div>

              {/* Statuts & Validation */}
              <div className="flex flex-col gap-3">
                <h4 className="font-bold text-sm text-primary uppercase border-b border-primary/20 pb-1">Statuts et Validation</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Classifié IA</span> {renderBool(selectedDocForDetails.is_classified)}</div>
                  <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Indexé RAG</span> {renderBool(selectedDocForDetails.rag_processed)}</div>
                  <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Validé Humain</span> {renderBool(selectedDocForDetails.is_validated)}</div>
                  <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Statut Validation</span> <span className="font-medium">{selectedDocForDetails.validation_status || '-'}</span></div>
                </div>
                <div className="text-sm mt-1"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Date de classification</span> {selectedDocForDetails.classified_at ? new Date(selectedDocForDetails.classified_at).toLocaleString('fr-FR') : '-'}</div>
                <div className="text-sm mt-2"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Règle de classification (IA)</span> {selectedDocForDetails.classification_reason || '-'}</div>
                <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Explication IA détaillée</span> <span className="italic text-xs text-on-surface-variant">{selectedDocForDetails.classification_description || '-'}</span></div>
              </div>

              {/* Métriques d'Extraction */}
              <div className="flex flex-col gap-3">
                <h4 className="font-bold text-sm text-tertiary uppercase border-b border-tertiary/20 pb-1">Métadonnées Physiques</h4>
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Pages</span> {selectedDocForDetails.page_count ?? '-'}</div>
                  <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Mots</span> {selectedDocForDetails.word_count ?? '-'}</div>
                  <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Taille</span> {selectedDocForDetails.file_size_mb ? `${selectedDocForDetails.file_size_mb.toFixed(2)} Mo` : '-'}</div>
                  <div className="text-sm"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Temps OCR</span> {selectedDocForDetails.ocr_duration_sec ? `${selectedDocForDetails.ocr_duration_sec.toFixed(2)}s` : '-'}</div>
                  <div className="text-sm col-span-2"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Temps Global (IA)</span> {selectedDocForDetails.response_time ? `${selectedDocForDetails.response_time.toFixed(2)}s` : '-'}</div>
                </div>
                <div className="text-sm mt-2"><span className="text-on-surface-variant font-medium block text-[11px] uppercase">Zones Administratives</span> <span className="font-mono text-xs">{selectedDocForDetails.administrative_zones ? JSON.stringify(selectedDocForDetails.administrative_zones) : '[]'}</span></div>
              </div>
              
              {/* Métadonnées JSON Brut */}
              <div className="flex flex-col gap-2">
                <h4 className="font-bold text-sm text-secondary uppercase border-b border-secondary/20 pb-1">Télémétrie IA (JSON)</h4>
                <div className="bg-[#1e1e1e] p-3 rounded-xl border border-outline-variant/20 max-h-40 overflow-y-auto">
                  {selectedDocForDetails.analysis_metadata ? (
                    <pre className="text-[#4ade80] text-[10px] whitespace-pre-wrap font-mono">
                      {JSON.stringify(selectedDocForDetails.analysis_metadata, null, 2)}
                    </pre>
                  ) : (
                    <span className="text-on-surface-variant text-xs">Aucune télémétrie disponible</span>
                  )}
                </div>
              </div>

            </div>

            {/* Texte Extrait Complet (Pleine largeur) */}
            <div className="mt-2 border-t border-outline-variant/20 pt-4">
              <h4 className="font-bold text-sm text-on-surface uppercase mb-2">Contenu Textuel Brut (Extrait OCR/Native)</h4>
              <div className="bg-surface-container-low p-4 rounded-xl border border-outline-variant/30 h-64 overflow-y-auto">
                {selectedDocForDetails.extracted_text ? (
                  <pre className="text-xs font-mono text-on-surface-variant whitespace-pre-wrap break-words leading-relaxed">
                    {selectedDocForDetails.extracted_text}
                  </pre>
                ) : (
                  <span className="text-on-surface-variant italic text-sm">Le texte brut n'a pas été stocké en base de données pour ce document.</span>
                )}
              </div>
            </div>
            
          </div>
        </div>
      )}

      {/* --- MODAL : ÉDITION DU DOCUMENT (PATCH) --- */}
      {selectedDocForEdit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-surface-container-lowest p-6 rounded-2xl shadow-xl border border-outline-variant/30 max-w-md w-full mx-4">
            <h3 className="text-xl font-bold mb-4">Modifier le document</h3>
            <p className="text-xs font-mono bg-surface-container p-2 rounded mb-4 truncate text-on-surface-variant">
              {selectedDocForEdit.file_name}
            </p>
            
            <div className="flex flex-col gap-4 mb-6">
              <div>
                <label className="block text-xs font-bold mb-1 text-on-surface">Type Détecté</label>
                <input 
                  type="text" 
                  value={editFormData.file_type} 
                  onChange={(e) => setEditFormData({...editFormData, file_type: e.target.value.toUpperCase()})}
                  className="w-full bg-surface-container border border-outline-variant/30 rounded-lg p-2 text-sm text-on-surface focus:border-primary outline-none"
                />
              </div>
              <div className="flex items-center gap-2">
                <input 
                  type="checkbox" 
                  id="is_class"
                  checked={editFormData.is_classified} 
                  onChange={(e) => setEditFormData({...editFormData, is_classified: e.target.checked})}
                  className="w-4 h-4 text-primary rounded"
                />
                <label htmlFor="is_class" className="text-sm font-medium">Considérer comme classifié</label>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <button onClick={() => setSelectedDocForEdit(null)} className="px-4 py-2 text-sm font-medium hover:bg-surface-container rounded-lg transition-colors">Annuler</button>
              <button onClick={handleSaveEdit} className="px-4 py-2 bg-primary text-on-primary text-sm font-medium rounded-lg shadow-sm hover:opacity-90 transition-opacity">
                Enregistrer (PATCH)
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}