import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function GlobalRagManager() {
  const { fetchWithAuth } = useAuth();
  
  const [tenders, setTenders] = useState([]);
  const [documents, setDocuments] = useState([]);
  
  // Pagination
  const [tPage, setTPage] = useState(1);
  const [dPage, setDPage] = useState(1);
  const limit = 10;

  // Iframe execution
  const [activeTarget, setActiveTarget] = useState(null); // { id, type: 'tender' | 'document' }
  const [logs, setLogs] = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    const fetchLists = async () => {
      try {
        const [resT, resD] = await Promise.all([
          fetchWithAuth('/api/tenders'),
          fetchWithAuth('/api/classifier/documents')
        ]);
        if (resT.ok) setTenders(await resT.json());
        if (resD.ok) {
          const d = await resD.json();
          setDocuments(d.items || []);
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchLists();
  }, []);

  const runAnalysis = async (type, id) => {
    setActiveTarget({ type, id });
    setLogs(["[Système] Démarrage..."]);
    
    if (wsRef.current) wsRef.current.close();
    wsRef.current = new WebSocket(`ws://localhost:8000/api/rag/ws/logs/${id}`);
    wsRef.current.onmessage = (e) => setLogs(prev => [...prev, `> ${e.data}`]);

    const endpoint = type === 'tender' ? `/api/rag/analyze-tender/${id}` : `/api/rag/analyze-document/${id}`;
    try {
      const res = await fetchWithAuth(endpoint, { method: 'POST' });
      const data = await res.json();
      setLogs(prev => [...prev, `[Serveur] ${data.message}`]);
    } catch (e) {
      setLogs(prev => [...prev, "[Erreur]"]);
    }
  };

  const logsHtml = `
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

  const currTenders = Array.isArray(tenders) ? tenders.slice((tPage-1)*limit, tPage*limit) : [];
  const currDocs = documents.slice((dPage-1)*limit, dPage*limit);

  return (
    <div className="p-6 max-w-7xl mx-auto flex flex-col gap-8">
      <h1 className="text-3xl font-bold">Gestionnaire RAG Global</h1>

      {/* Terminal Actif */}
      {activeTarget && (
        <div className="bg-surface-container-lowest p-4 rounded-xl border border-primary/30 h-[400px] flex flex-col shadow-sm">
          <div className="flex justify-between items-center mb-2">
            <span className="font-bold text-sm uppercase">Logs en direct ({activeTarget.type})</span>
            <button onClick={() => { setActiveTarget(null); wsRef.current?.close(); }} className="bg-error text-on-error px-3 py-1 rounded text-xs font-bold">Fermer</button>
          </div>
          <iframe srcDoc={logsHtml} className="flex-1 w-full border-none bg-[#1e1e1e] rounded-lg" />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Table Tenders */}
        <div className="bg-surface-container-lowest p-4 rounded-xl shadow-sm border border-outline-variant/30">
          <h2 className="font-bold mb-4">Tenders Disponibles</h2>
          <table className="w-full text-left text-sm mb-4">
            <thead><tr className="border-b"><th className="p-2">Réf.</th><th className="p-2">UUID</th><th className="p-2">Action</th></tr></thead>
            <tbody className="divide-y divide-outline-variant/10">
              {currTenders.map(t => (
                <tr key={t.id}>
                  <td className="p-2">{t.reference}</td><td className="p-2 font-mono text-[10px]">{t.id}</td>
                  <td className="p-2"><button onClick={() => runAnalysis('tender', t.id)} className="bg-primary text-on-primary px-2 py-1 rounded text-xs">Lancer</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex justify-between text-sm">
            <button onClick={() => setTPage(p => Math.max(1, p-1))} disabled={tPage===1}>Précédent</button>
            <span>Page {tPage}</span>
            <button onClick={() => setTPage(p => p+1)}>Suivant</button>
          </div>
        </div>

        {/* Table Documents */}
        <div className="bg-surface-container-lowest p-4 rounded-xl shadow-sm border border-outline-variant/30">
          <h2 className="font-bold mb-4">Documents Disponibles</h2>
          <table className="w-full text-left text-sm mb-4">
            <thead><tr className="border-b"><th className="p-2">Fichier</th><th className="p-2">UUID</th><th className="p-2">Action</th></tr></thead>
            <tbody className="divide-y divide-outline-variant/10">
              {currDocs.map(d => (
                <tr key={d.id}>
                  <td className="p-2 truncate max-w-[150px]">{d.file_name}</td><td className="p-2 font-mono text-[10px]">{d.id}</td>
                  <td className="p-2"><button onClick={() => runAnalysis('document', d.id)} className="bg-secondary text-on-secondary px-2 py-1 rounded text-xs">Lancer</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex justify-between text-sm">
            <button onClick={() => setDPage(p => Math.max(1, p-1))} disabled={dPage===1}>Précédent</button>
            <span>Page {dPage}</span>
            <button onClick={() => setDPage(p => p+1)}>Suivant</button>
          </div>
        </div>
      </div>
    </div>
  );
}