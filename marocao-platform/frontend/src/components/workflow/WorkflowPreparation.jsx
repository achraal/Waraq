import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function WorkflowPreparation({ tenderId }) {
  const { fetchWithAuth, user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });

  const fetchPrep = async () => {
    try {
      const res = await fetchWithAuth(`/api/workflows/tenders/${tenderId}/preparation`);
      if (res.ok) setData(await res.json());
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => { fetchPrep(); }, [tenderId]);

  const handleScan = async () => {
    setLoading(true);
    setMsg({ type: 'info', text: 'Scan et inventaire en cours...' });
    try {
      const res = await fetchWithAuth(`/api/workflows/tenders/${tenderId}/preparation/scan`, {
        method: 'POST',
        body: JSON.stringify({ user_id: user.id })
      });
      if (res.ok) {
        setMsg({ type: 'success', text: 'Scan terminé avec succès.' });
        fetchPrep();
      } else {
        const error = await res.json();
        setMsg({ type: 'error', text: error.detail || 'Erreur lors du scan.' });
      }
    } catch (err) {
      setMsg({ type: 'error', text: 'Erreur réseau.' });
    }
    setLoading(false);
  };

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-bold text-primary">Préparation et Inventaire</h2>
      
      {msg.text && (
        <div className={`p-3 rounded-lg text-sm font-bold ${msg.type === 'error' ? 'bg-red-500/10 text-red-600' : msg.type === 'success' ? 'bg-green-500/10 text-green-600' : 'bg-blue-500/10 text-blue-600'}`}>
          {msg.text}
        </div>
      )}

      <button onClick={handleScan} disabled={loading} className="self-start bg-primary text-on-primary px-4 py-2 rounded-lg font-bold shadow-sm disabled:opacity-50">
        {loading ? 'Analyse...' : 'Lancer le Scan des Documents'}
      </button>

      {data && (
        <div className="bg-surface-container p-4 rounded-lg overflow-auto max-h-[400px]">
          <pre className="text-xs font-mono">{JSON.stringify(data, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}