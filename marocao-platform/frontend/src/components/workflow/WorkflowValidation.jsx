import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function WorkflowValidation({ tenderId }) {
  const { fetchWithAuth } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [msg, setMsg] = useState({ type: '', text: '' });

  const loadDocs = async () => {
    try {
      const res = await fetchWithAuth(`/api/workflows/tenders/${tenderId}/preparation`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []); // Ajuste selon la structure de ta réponse
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => { loadDocs(); }, [tenderId]);

  const handleAction = async (docId, action) => {
    setMsg({ type: '', text: '' });
    try {
      if (action === 'delete') {
        const res = await fetchWithAuth(`/api/workflows/preparation/documents/${docId}`, { method: 'DELETE' });
        if (res.ok) setMsg({ type: 'success', text: 'Document supprimé.' });
        else setMsg({ type: 'error', text: 'Erreur lors de la suppression.' });
      } else {
        const isValid = action === 'valid';
        const res = await fetchWithAuth(`/api/workflows/preparation/documents/${docId}/validate`, {
          method: 'POST',
          body: JSON.stringify({ valid: isValid, message: isValid ? 'OK' : 'Rejeté manuellement' })
        });
        if (res.ok) setMsg({ type: 'success', text: `Document marqué comme ${isValid ? 'Valide' : 'Invalide'}.` });
        else setMsg({ type: 'error', text: 'Erreur lors de la validation.' });
      }
      loadDocs();
    } catch (err) {
      setMsg({ type: 'error', text: 'Erreur réseau.' });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-bold text-primary">Validation Manuelle</h2>

      {msg.text && (
        <div className={`p-3 rounded-lg text-sm font-bold ${msg.type === 'error' ? 'bg-red-500/10 text-red-600' : 'bg-green-500/10 text-green-600'}`}>
          {msg.text}
        </div>
      )}

      {documents.length === 0 ? <p className="text-sm">Aucun document trouvé. Lancez le scan d'abord.</p> : (
        <table className="w-full text-left text-sm border border-outline-variant/30 rounded-lg overflow-hidden">
          <thead className="bg-surface-container-low text-xs uppercase">
            <tr><th className="p-3">Fichier</th><th className="p-3">Statut</th><th className="p-3">Actions</th></tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/20">
            {documents.map(doc => (
              <tr key={doc.id}>
                <td className="p-3 font-bold truncate max-w-[200px]">{doc.file_name || doc.id}</td>
                <td className="p-3">
                  <span className={`px-2 py-1 rounded text-[10px] font-bold ${doc.is_valid ? 'bg-green-500/20 text-green-600' : 'bg-red-500/20 text-red-600'}`}>
                    {doc.is_valid ? 'VALIDE' : 'INVALIDE'}
                  </span>
                </td>
                <td className="p-3 flex gap-2">
                  <button onClick={() => handleAction(doc.id, 'valid')} className="bg-green-500 text-white px-2 py-1 rounded text-xs font-bold">Valider</button>
                  <button onClick={() => handleAction(doc.id, 'invalid')} className="bg-orange-500 text-white px-2 py-1 rounded text-xs font-bold">Invalider</button>
                  <button onClick={() => handleAction(doc.id, 'delete')} className="bg-red-500 text-white px-2 py-1 rounded text-xs font-bold">Supprimer</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}