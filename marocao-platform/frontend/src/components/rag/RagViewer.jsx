import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function RagViewer() {
  const { fetchWithAuth } = useAuth();
  
  const [tenderId, setTenderId] = useState('');
  const [docId, setDocId] = useState('');
  
  const [stats, setStats] = useState(null);
  const [summary, setSummary] = useState(null);

  const fetchStats = async () => {
    if (!tenderId) return;
    try {
      const res = await fetchWithAuth(`/api/rag/stats/${tenderId}`);
      if (res.ok) setStats(await res.json());
      else alert("Aucune statistique RAG trouvée pour ce Tender.");
    } catch (err) {
      console.error(err);
    }
  };

  const fetchSummary = async () => {
    if (!docId) return;
    try {
      const res = await fetchWithAuth(`/api/rag/summary/${docId}`);
      if (res.ok) setSummary(await res.json());
      else alert("Aucun résumé trouvé pour ce Document.");
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-bold">Visionneuse RAG (Résultats & Stats)</h1>
        <p className="text-sm text-on-surface-variant">Consultez les résultats de l'Intelligence Métier.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Panneau Stats */}
        <div className="bg-surface-container-lowest p-6 rounded-2xl shadow-sm border border-outline-variant/30">
          <h2 className="text-lg font-bold mb-4 text-primary">Stats RAG (Tender)</h2>
          <div className="flex gap-2 mb-4">
            <input type="text" placeholder="UUID du Tender..." value={tenderId} onChange={e => setTenderId(e.target.value)} className="flex-1 p-2 rounded bg-surface-container border border-outline-variant/30 text-sm outline-none" />
            <button onClick={fetchStats} className="bg-primary text-on-primary px-4 py-2 rounded text-sm font-bold">Chercher</button>
          </div>
          {stats && (
            <div className="bg-surface-container p-4 rounded text-sm flex flex-col gap-2">
              <div><span className="font-bold">Statut :</span> {stats.status}</div>
              <div><span className="font-bold">Terminés :</span> {stats.documents.completed} / {stats.documents.total}</div>
            </div>
          )}
        </div>

        {/* Panneau Résumé */}
        <div className="bg-surface-container-lowest p-6 rounded-2xl shadow-sm border border-outline-variant/30">
          <h2 className="text-lg font-bold mb-4 text-secondary">Résumé Métier (Document)</h2>
          <div className="flex gap-2 mb-4">
            <input type="text" placeholder="UUID du Document..." value={docId} onChange={e => setDocId(e.target.value)} className="flex-1 p-2 rounded bg-surface-container border border-outline-variant/30 text-sm outline-none" />
            <button onClick={fetchSummary} className="bg-secondary text-on-secondary px-4 py-2 rounded text-sm font-bold">Chercher</button>
          </div>
          {summary && (
            <div className="bg-surface-container p-4 rounded text-sm overflow-y-auto max-h-64">
              <pre className="whitespace-pre-wrap font-sans">{JSON.stringify(summary, null, 2)}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}