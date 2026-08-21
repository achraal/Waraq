import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function TenderDocumentClassifier() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { fetchWithAuth } = useAuth();
  
  const [tender, setTender] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  
  // États pour la barre de progression et les logs
  const [progressData, setProgressData] = useState(null);
  const [logs, setLogs] = useState([]); // <-- AJOUT POUR LES LOGS
  
  const [notification, setNotification] = useState({ show: false, message: '', type: '' });
  const [confirmDialog, setConfirmDialog] = useState({ show: false, documentId: null });
  const wsRef = useRef(null);
  const [isCompleted, setIsCompleted] = useState(false);

  // --- NOUVELLE FONCTION POUR FERMER MANUELLEMENT ---
  const handleCloseLogs = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setProcessing(false);
    setIsCompleted(false);
    setProgressData(null);
  };

  const showMessage = (msg, type = 'info') => {
    setNotification({ show: true, message: msg, type });
    setTimeout(() => setNotification({ show: false, message: '', type: '' }), 5000);
  };

  const fetchTenderData = async () => {
    try {
      const res = await fetchWithAuth(`/api/tenders/${id}`);
      if (res.ok) {
        const data = await res.json();
        setTender(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenderData();
  }, [id]);

  // EFFET DE POLLING
  // EFFET DE POLLING
  useEffect(() => {
    let interval;
    
    // On poll uniquement si on est en "processing" ET que ce n'est pas encore "completed"
    if (processing && !isCompleted) {
      interval = setInterval(async () => {
        try {
          const res = await fetchWithAuth(`/api/classifier/status`);
          
          if (res.ok) {
            const data = await res.json();
            setProgressData(data);
            
            // Met à jour le tableau en temps réel
            fetchTenderData(); 
            
            // CONDITION D'ARRÊT :
            // On s'assure qu'on s'arrête si le statut est 'idle' OU si 100% des documents sont classifiés.
            // (Utiliser classified === total est plus sûr que pending === 0, car au tout début pending peut être 0 avant le démarrage)
            const isFinished = data.status === 'idle' || 
                               (data.total_documents > 0 && data.classified_documents === data.total_documents);

            if (isFinished) {
              setLogs(prev => [...prev, `[Succès] Traitement IA terminé avec succès.`]);
              setIsCompleted(true); // Affiche le bouton "Fermer le terminal"
              
              // 1. ARRÊT IMMÉDIAT DU POLLING
              clearInterval(interval);
              
              // 2. FERMETURE DU WEBSOCKET (car le backend a fini d'envoyer des logs)
              if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
              }
            }
          }
        } catch (err) {
          console.error("Erreur récupération statut", err);
        }
      }, 2000);
    }
    
    return () => {
      clearInterval(interval);
    };
  }, [processing, isCompleted, fetchWithAuth]);
    

  const handleClassifyTender = async () => {
    setProcessing(true);
    setIsCompleted(false);
    setProgressData({ progress_percentage: 0, classified_documents: 0, total_documents: tender.documents?.length || 0 });
    
    setLogs(["[Système] Démarrage de l'analyse IA...", "[Système] Connexion aux logs du serveur..."]);
    
    // On ferme l'ancienne connexion si elle existe, puis on ouvre la nouvelle
    if (wsRef.current) wsRef.current.close();
    wsRef.current = new WebSocket(`ws://localhost:8000/api/classifier/ws/logs/${id}`);
    
    wsRef.current.onmessage = (event) => {
      setLogs(prev => [...prev, `> ${event.data}`]);
    };
    
    try {
      const res = await fetchWithAuth(`/api/classifier/classify-documents/tender/${id}`, { method: 'POST' });
      const data = await res.json();
      
      const estimationText = data.estimation?.formatted_estimation ? `\n\n${data.estimation.formatted_estimation}` : '';
      showMessage(`${data.message}${estimationText}`, 'success');
      
      // ATTENTION : On ne met plus setProcessing(false) ici ! 
      // On laisse l'IA travailler en tâche de fond.
    } catch (err) {
      showMessage("Erreur lors du lancement de la classification.", 'error');
      setLogs(prev => [...prev, "[Erreur] La connexion au serveur a échoué."]);
      setProcessing(false); // On arrête seulement si ça a planté au démarrage
    }
  };

  const requestUnclassify = (documentId) => {
    setConfirmDialog({ show: true, documentId });
  };

  const executeUnclassify = async () => {
    const docId = confirmDialog.documentId;
    setConfirmDialog({ show: false, documentId: null });
    
    try {
      const res = await fetchWithAuth(`/api/classifier/unclassify`, { 
        method: 'POST',
        body: JSON.stringify({ document_ids: [docId] }) 
      });

      if (res.ok) {
        showMessage("Classification réinitialisée avec succès.", 'success');
        fetchTenderData();
      } else {
        showMessage("Erreur lors de la dé-classification.", 'error');
      }
    } catch (err) {
      showMessage("Erreur de connexion au serveur.", 'error');
    }
  };

  if (loading) return <div className="p-10 text-center">Chargement des documents...</div>;
  if (!tender) return <div className="p-10 text-center text-error">Appel d'offres introuvable.</div>;

  const isAllClassified = tender.documents?.length > 0 && tender.documents.every(doc => doc.is_classified);

  // --- GÉNÉRATION DU HTML POUR L'IFRAME ---
  const logsHtmlContent = `
    <!DOCTYPE html>
    <html>
      <head>
        <style>
          body {
            background-color: #1e1e1e;
            color: #4ade80;
            font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
            font-size: 13px;
            padding: 16px;
            margin: 0;
            line-height: 1.6;
          }
          div { margin-bottom: 4px; }
        </style>
        <script>
          const observer = new MutationObserver(() => window.scrollTo(0, document.body.scrollHeight));
          window.onload = () => {
            observer.observe(document.body, { childList: true, subtree: true });
            window.scrollTo(0, document.body.scrollHeight);
          }
        </script>
      </head>
      <body>
        ${logs.map(log => `<div>${log}</div>`).join('')}
      </body>
    </html>
  `;

  return (
    <div className="p-6 max-w-6xl mx-auto flex flex-col gap-6 relative">
      
      {/* Fenêtre Modale de Confirmation */}
      {confirmDialog.show && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-surface-container-lowest p-6 rounded-2xl shadow-xl border border-outline-variant/30 max-w-md w-full mx-4">
            <h3 className="text-xl font-bold text-on-surface mb-2 flex items-center gap-2">
              <span className="material-symbols-outlined text-error text-[28px]">warning</span>
              Réinitialiser ?
            </h3>
            <p className="text-on-surface-variant mb-6 text-sm">
              Voulez-vous vraiment réinitialiser la classification de ce document ? Toutes les données validées seront perdues.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setConfirmDialog({ show: false, documentId: null })} className="px-4 py-2 font-medium text-on-surface-variant hover:bg-surface-container rounded-lg transition-colors">Annuler</button>
              <button onClick={executeUnclassify} className="px-4 py-2 bg-error text-on-error font-medium hover:bg-error/90 rounded-lg transition-colors shadow-sm">Oui, réinitialiser</button>
            </div>
          </div>
        </div>
      )}

      {/* Zone d'en-tête */}
      <div className="flex items-center justify-between">
        <div>
          <button onClick={() => navigate(`/tenders/${id}`)} className="text-sm flex items-center gap-1 text-on-surface-variant hover:text-primary mb-2 transition-colors">
            <span className="material-symbols-outlined text-sm">arrow_back</span> Retour au Tender
          </button>
          <h1 className="text-2xl font-bold text-on-surface">Classification des documents</h1>
          <p className="text-sm text-on-surface-variant">Réf: {tender.reference}</p>
        </div>
        
        {!isAllClassified && (
          <button onClick={handleClassifyTender} disabled={processing} className="flex items-center gap-2 px-5 py-2.5 bg-primary text-on-primary rounded-lg font-medium shadow-sm hover:opacity-90 disabled:opacity-50 transition-all">
            <span className={`material-symbols-outlined ${processing ? 'animate-spin' : ''}`}>auto_awesome</span>
            {processing ? 'Analyse IA en cours...' : 'Classifier les documents'}
          </button>
        )}
      </div>

      {/* Notification intégrée */}
      {notification.show && (
        <div className={`p-4 rounded-lg flex items-start gap-3 shadow-sm ${notification.type === 'error' ? 'bg-error/10 text-error border border-error/20' : 'bg-primary/10 text-primary border border-primary/20'}`}>
          <span className="material-symbols-outlined mt-0.5">{notification.type === 'error' ? 'error' : 'check_circle'}</span>
          <div className="whitespace-pre-line text-sm font-medium">{notification.message}</div>
        </div>
      )}

      {/* BARRE DE PROGRESSION ET TERMINAL DE LOGS */}
      {processing && (
        <div className="flex flex-col gap-4 animate-fade-in">
          
          {/* Barre de progression */}
          {progressData && (
            <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/30 shadow-sm flex flex-col gap-4">
              <div className="flex justify-between items-center text-sm font-bold">
                <span className={`flex items-center gap-2 ${isCompleted ? 'text-primary' : 'text-primary'}`}>
                  {isCompleted ? (
                    <span className="material-symbols-outlined text-[20px]">check_circle</span>
                  ) : (
                    <span className="material-symbols-outlined animate-spin text-[20px]">sync</span>
                  )}
                  {isCompleted ? 'Traitement terminé !' : 'Traitement par l\'IA en cours...'}
                </span>
                <span className="text-secondary">
                  {progressData.classified_documents} / {progressData.total_documents} documents ({progressData.progress_percentage}%)
                </span>
              </div>
              <div className="w-full bg-surface-container h-3 rounded-full overflow-hidden">
                <div className="bg-primary h-full transition-all duration-500 ease-out" style={{ width: `${progressData.progress_percentage}%` }}></div>
              </div>
            </div>
          )}

          {/* Iframe des Logs en direct */}
          <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-sm flex flex-col overflow-hidden h-64">
            <div className="bg-surface-container-low p-2 border-b border-outline-variant/20 flex items-center gap-2">
              <span className="material-symbols-outlined text-secondary text-sm">terminal</span>
              <h3 className="font-bold text-xs uppercase text-on-surface-variant tracking-wider">Terminal de Classification</h3>
              
              {/* Affichage dynamique en haut à droite du terminal */}
              <div className="ml-auto flex items-center gap-3">
                {!isCompleted ? (
                  <span className="flex items-center gap-2 text-xs font-bold text-primary animate-pulse">
                    <span className="w-2 h-2 rounded-full bg-primary"></span> En direct
                  </span>
                ) : (
                  <button 
                    onClick={handleCloseLogs} 
                    className="flex items-center gap-1 text-xs font-bold bg-primary text-on-primary px-3 py-1.5 rounded-lg hover:bg-primary/90 transition-colors shadow-sm"
                  >
                    <span className="material-symbols-outlined text-[16px]">close</span>
                    Fermer le terminal
                  </button>
                )}
              </div>
            </div>
            
            <iframe 
              title="Logs IA"
              srcDoc={logsHtmlContent}
              className="flex-1 w-full border-none bg-[#1e1e1e]"
              sandbox="allow-scripts"
            />
          </div>

        </div>
      )}

      {/* Tableau des documents */}
      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 overflow-hidden shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="bg-surface-container-low text-xs uppercase text-on-surface-variant">
            <tr>
              <th className="p-4">Fichier Source</th>
              <th className="p-4 text-center">Statut IA</th>
              <th className="p-4">Type Détecté</th>
              <th className="p-4 text-center">Validation</th>
              <th className="p-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/20">
            {tender.documents?.map(doc => (
              <tr key={doc.id} className="hover:bg-surface-container-low/30 transition-colors">
                <td className="p-4 font-mono text-xs max-w-xs truncate" title={doc.file_name}>{doc.file_name}</td>
                <td className="p-4 text-center">
                  {doc.is_classified ? (
                    <span className="bg-primary/10 text-primary px-2 py-1 rounded text-xs font-bold border border-primary/20">CLASSIFIÉ</span>
                  ) : (
                    <span className="bg-surface-variant text-on-surface-variant px-2 py-1 rounded text-xs border border-outline-variant/30">EN ATTENTE</span>
                  )}
                </td>
                <td className="p-4 font-bold text-secondary">{doc.file_type || '-'}</td>
                <td className="p-4 text-center">
                  {doc.is_validated ? (
                    <span className="text-primary text-xs font-bold flex items-center justify-center gap-1">
                      <span className="material-symbols-outlined text-sm">verified_user</span> {doc.validation_status}
                    </span>
                  ) : doc.is_classified ? (
                    <span className="text-error text-xs flex items-center justify-center gap-1">
                      <span className="material-symbols-outlined text-sm">pending_actions</span> À vérifier
                    </span>
                  ) : (
                    <span className="text-on-surface-variant/50">-</span>
                  )}
                </td>
                <td className="p-4 flex justify-center gap-4">
                  <Link 
                    to={`/tenders/${id}/document/${doc.id}/validate`}
                    className="text-primary hover:text-primary/70 transition-colors flex items-center"
                    title="Voir et Valider"
                  >
                    <span className="material-symbols-outlined text-[22px]">fact_check</span>
                  </Link>
                  <button 
                    onClick={() => requestUnclassify(doc.id)} 
                    className="text-error hover:text-error/70 transition-colors flex items-center"
                    title="Réinitialiser la classification"
                  >
                    <span className="material-symbols-outlined text-[22px]">restart_alt</span>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}