import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function WorkflowBDP({ tenderId }) {
  const { fetchWithAuth } = useAuth();
  const [bdpData, setBdpData] = useState(null);
  const [msg, setMsg] = useState({ type: '', text: '' });
  const [loading, setLoading] = useState(false);
  const [jsonInput, setJsonInput] = useState('');

  const analyzeBdp = async () => {
    setLoading(true);
    setMsg({ type: 'info', text: 'Analyse du BDP en cours...' });
    try {
      const res = await fetchWithAuth(`/api/workflows/tenders/${tenderId}/bdp/analyze`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setBdpData(data);
        setJsonInput(JSON.stringify(data.items || [], null, 2));
        setMsg({ type: 'success', text: 'BDP Analysé.' });
      } else {
        setMsg({ type: 'error', text: 'Erreur lors de l\'analyse BDP.' });
      }
    } catch (err) {
      setMsg({ type: 'error', text: 'Erreur réseau.' });
    }
    setLoading(false);
  };

  const fillBdp = async () => {
    if (!bdpData?.document_id) return setMsg({ type: 'error', text: 'Aucun document BDP détecté.' });
    setLoading(true);
    try {
      const parsedValues = JSON.parse(jsonInput);
      const res = await fetchWithAuth(`/api/workflows/preparation/documents/${bdpData.document_id}/bdp/fill`, {
        method: 'POST',
        body: JSON.stringify({ values: parsedValues })
      });
      if (res.ok) setMsg({ type: 'success', text: 'Prix injectés et BDP généré.' });
      else setMsg({ type: 'error', text: 'Erreur lors du remplissage.' });
    } catch (err) {
      setMsg({ type: 'error', text: 'Format JSON invalide ou erreur réseau.' });
    }
    setLoading(false);
  };

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-bold text-primary">Bordereau des Prix (BDP)</h2>
      
      {msg.text && (
        <div className={`p-3 rounded-lg text-sm font-bold ${msg.type === 'error' ? 'bg-red-500/10 text-red-600' : msg.type === 'success' ? 'bg-green-500/10 text-green-600' : 'bg-blue-500/10 text-blue-600'}`}>
          {msg.text}
        </div>
      )}

      <button onClick={analyzeBdp} disabled={loading} className="self-start bg-primary text-on-primary px-4 py-2 rounded-lg font-bold shadow-sm">
        {loading ? 'Traitement...' : 'Analyser le BDP (Extraction des articles)'}
      </button>

      {bdpData && (
        <div className="mt-4">
          <label className="block text-sm font-bold mb-2">Saisir les prix et détails (Éditeur JSON pour les valeurs array) :</label>
          <textarea 
            className="w-full h-64 p-3 font-mono text-sm bg-surface-container border border-outline-variant/30 rounded-lg outline-none"
            value={jsonInput}
            onChange={(e) => setJsonInput(e.target.value)}
          />
          <button onClick={fillBdp} disabled={loading} className="mt-4 bg-secondary text-on-secondary px-4 py-2 rounded-lg font-bold shadow-sm">
            Remplir et Sauvegarder BDP
          </button>
        </div>
      )}
    </div>
  );
}