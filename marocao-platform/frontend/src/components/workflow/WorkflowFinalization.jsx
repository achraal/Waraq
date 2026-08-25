import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function WorkflowFinalization({ tenderId }) {
  const { fetchWithAuth, user } = useAuth();
  const [msg, setMsg] = useState({ type: '', text: '' });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const finalize = async () => {
    setLoading(true);
    setMsg({ type: 'info', text: 'Finalisation et génération du dossier complet en cours...' });
    try {
      const res = await fetchWithAuth(`/api/workflows/tenders/${tenderId}/finalize`, {
        method: 'POST',
        body: JSON.stringify({ user_id: user.id })
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
        setMsg({ type: 'success', text: 'Dossier finalisé avec succès !' });
      } else {
        const error = await res.json();
        setMsg({ type: 'error', text: error.detail || 'Erreur lors de la finalisation.' });
      }
    } catch (err) {
      setMsg({ type: 'error', text: 'Erreur réseau.' });
    }
    setLoading(false);
  };

  return (
    <div className="flex flex-col gap-4 text-center items-center">
      <span className="material-symbols-outlined text-6xl text-green-500 mb-2">verified</span>
      <h2 className="text-2xl font-bold text-primary">Finalisation du Dossier</h2>
      <p className="text-sm text-on-surface-variant max-w-lg mb-4">
        Cette étape va vérifier l'intégrité de toutes les pièces, convertir les documents Word en PDF, 
        et packager les livrables finaux prêts à être soumis.
      </p>

      {msg.text && (
        <div className={`w-full max-w-lg p-3 rounded-lg text-sm font-bold ${msg.type === 'error' ? 'bg-red-500/10 text-red-600' : msg.type === 'success' ? 'bg-green-500/10 text-green-600' : 'bg-blue-500/10 text-blue-600'}`}>
          {msg.text}
        </div>
      )}

      <button onClick={finalize} disabled={loading} className="bg-primary text-on-primary px-8 py-3 rounded-xl font-black shadow-lg hover:opacity-90 transition-opacity">
        {loading ? 'Traitement en cours...' : 'Finaliser & Packager le Dossier'}
      </button>

      {result && (
        <div className="mt-8 bg-surface-container text-left w-full max-w-3xl p-6 rounded-xl border border-outline-variant/30">
          <h3 className="font-bold text-lg mb-2">Résumé de Finalisation</h3>
          <pre className="text-xs font-mono overflow-auto max-h-64 whitespace-pre-wrap">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}