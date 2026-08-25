import React, { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function TenderRagRunner() {
  const { tenderId } = useParams(); // Récupéré depuis l'URL
  const navigate = useNavigate();
  const { fetchWithAuth } = useAuth();
  
  const [processing, setProcessing] = useState(false);
  const [logs, setLogs] = useState([]);
  const wsRef = useRef(null);

  const startTenderAnalysis = async () => {
    setProcessing(true);
    setLogs(["[Système] Connexion au flux de traitement RAG..."]);

    if (wsRef.current) wsRef.current.close();
    wsRef.current = new WebSocket(`ws://localhost:8000/api/rag/ws/logs/${tenderId}`);
    
    wsRef.current.onmessage = (event) => {
      setLogs(prev => [...prev, `> ${event.data}`]);
    };

    try {
      const res = await fetchWithAuth(`/api/rag/analyze-tender/${tenderId}`, { method: 'POST' });
      const data = await res.json();
      setLogs(prev => [...prev, `[Serveur] ${data.message}`]);
    } catch (err) {
      setLogs(prev => [...prev, "[Erreur] Échec de la requête d'analyse."]);
    }
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
      <div className="flex justify-between items-center bg-surface-container-lowest p-6 rounded-2xl shadow-sm border border-outline-variant/30">
        <div>
          <h1 className="text-2xl font-bold">Analyse RAG - Appel d'Offres</h1>
          <p className="text-sm font-mono text-on-surface-variant mt-1">UUID : {tenderId}</p>
        </div>
        <button onClick={() => navigate(-1)} className="text-sm font-bold bg-surface-container px-4 py-2 rounded-lg">Retour</button>
      </div>

      {!processing ? (
        <div className="text-center bg-surface-container-lowest p-10 rounded-2xl shadow-sm border border-outline-variant/30">
          <p className="mb-6">Cliquez ci-dessous pour déclencher l'analyse RAG (Extraction, Embedding, Vectorisation, IA Générative) pour tous les documents stratégiques de ce dossier.</p>
          <button onClick={startTenderAnalysis} className="bg-primary text-on-primary px-6 py-3 rounded-xl font-bold shadow-md">
            Lancer l'Analyse du Tender
          </button>
        </div>
      ) : (
        <div className="flex flex-col h-[500px] bg-surface-container-lowest rounded-2xl border border-outline-variant/30 overflow-hidden shadow-sm">
          <div className="p-3 bg-surface-container-low border-b font-bold text-sm uppercase flex justify-between items-center">
            <span>Terminal d'Exécution RAG</span>
            <span className="flex items-center gap-2 text-primary text-xs"><span className="w-2 h-2 bg-primary rounded-full animate-pulse"></span>En direct</span>
          </div>
          <iframe srcDoc={logsHtmlContent} className="flex-1 w-full border-none bg-[#1e1e1e]" />
        </div>
      )}
    </div>
  );
}