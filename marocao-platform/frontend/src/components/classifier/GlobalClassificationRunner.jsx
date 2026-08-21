import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function GlobalClassificationRunner() {
  const { fetchWithAuth } = useAuth();
  
  const [processing, setProcessing] = useState(false);
  const [status, setStatus] = useState({ status: 'idle', progress_percentage: 0, classified_documents: 0, total_documents: 0 });
  
  const [logs, setLogs] = useState([]);
  const wsRef = useRef(null);
  const [isCompleted, setIsCompleted] = useState(false);

  // Polling du statut en temps réel
  useEffect(() => {
    let interval;
    if (processing && !isCompleted) {
      interval = setInterval(async () => {
        try {
          const res = await fetchWithAuth('/api/classifier/status');
          if (res.ok) {
            const data = await res.json();
            setStatus(data);
            
            // Condition d'arrêt
            if (data.status === 'idle' || data.pending_documents === 0) {
              setLogs(prev => [...prev, `[Succès] Traitement IA global terminé avec succès.`]);
              setIsCompleted(true);
            }
          }
        } catch (err) {
          console.error("Erreur récupération statut:", err);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [processing, isCompleted, fetchWithAuth]);

  // Lancement
  const handleStartGlobalClassification = async () => {
    setProcessing(true);
    setIsCompleted(false);
    setStatus({ status: 'processing', progress_percentage: 0, classified_documents: 0, total_documents: 0 });
    
    setLogs(["[Système] Démarrage du moteur IA global...", "[Système] Connexion aux logs globaux..."]);
    
    // WebSockets pour les logs globaux
    if (wsRef.current) wsRef.current.close();
    wsRef.current = new WebSocket(`ws://localhost:8000/api/classifier/ws/logs/global`);
    
    wsRef.current.onmessage = (event) => {
      setLogs(prev => [...prev, `> ${event.data}`]);
    };

    try {
      const res = await fetchWithAuth('/api/classifier/classify-documents', { method: 'POST' });
      const data = await res.json();
      setLogs(prev => [...prev, `[Info] ${data.message} ${data.estimation?.formatted_estimation || ''}`]);
    } catch (err) {
      alert("Erreur lors du lancement de la classification.");
      setLogs(prev => [...prev, "[Erreur] Échec de la connexion."]);
      setProcessing(false);
    }
  };

  const handleCloseLogs = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setProcessing(false);
    setIsCompleted(false);
    setStatus({ status: 'idle', progress_percentage: 0 });
  };

  const logsHtmlContent = `
    <!DOCTYPE html><html><head><style>
      body { background-color: #1e1e1e; color: #4ade80; font-family: monospace; font-size: 13px; padding: 16px; margin: 0; }
      div { margin-bottom: 4px; }
    </style><script>
      const obs = new MutationObserver(() => window.scrollTo(0, document.body.scrollHeight));
      window.onload = () => { obs.observe(document.body, { childList: true }); window.scrollTo(0, document.body.scrollHeight); }
    </script></head><body>
      ${logs.map(l => `<div>${l}</div>`).join('')}
    </body></html>
  `;

  return (
    <div className="p-6 max-w-4xl mx-auto flex flex-col gap-6">
      <div className="flex justify-between items-center bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/30 shadow-sm">
        <div>
          <h2 className="text-xl font-bold">Lanceur de Classification</h2>
          <p className="text-sm text-on-surface-variant">Traiter tous les documents en attente.</p>
        </div>
        <button 
          onClick={handleStartGlobalClassification} 
          disabled={status.status === 'processing' || processing}
          className="flex items-center gap-2 px-5 py-2.5 bg-primary text-on-primary rounded-lg font-medium shadow-sm hover:opacity-90 disabled:opacity-50"
        >
          <span className={`material-symbols-outlined ${(status.status === 'processing' || processing) ? 'animate-spin' : ''}`}>sync</span>
          {(status.status === 'processing' || processing) ? 'Traitement en cours...' : 'Lancer le traitement'}
        </button>
      </div>

      {processing && (
        <div className="flex flex-col gap-4 animate-fade-in">
          {/* Progress Bar */}
          <div className="bg-surface-container-lowest p-4 rounded-xl border border-primary/30 shadow-sm">
            <div className="flex justify-between text-sm font-bold text-primary mb-2">
              <span>{isCompleted ? 'Terminé !' : 'Progression'}</span>
              <span>{status.classified_documents} / {status.total_documents} ({status.progress_percentage}%)</span>
            </div>
            <div className="w-full bg-surface-container h-2.5 rounded-full overflow-hidden">
              <div className="bg-primary h-full transition-all duration-500" style={{ width: `${status.progress_percentage}%` }}></div>
            </div>
          </div>

          {/* Iframe Terminal */}
          <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 overflow-hidden shadow-sm h-72 flex flex-col">
            <div className="bg-surface-container-low p-2 border-b flex justify-between items-center">
              <span className="font-bold text-xs uppercase text-on-surface-variant px-2">Terminal en direct</span>
              {isCompleted && (
                <button onClick={handleCloseLogs} className="text-xs bg-primary text-on-primary px-3 py-1 rounded-lg">Fermer</button>
              )}
            </div>
            <iframe srcDoc={logsHtmlContent} className="flex-1 w-full bg-[#1e1e1e] border-none" sandbox="allow-scripts" />
          </div>
        </div>
      )}
    </div>
  );
}