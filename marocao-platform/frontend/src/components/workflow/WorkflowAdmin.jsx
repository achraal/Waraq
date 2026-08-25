import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function WorkflowAdmin({ tenderId }) {
  const { fetchWithAuth } = useAuth();
  const [docId, setDocId] = useState('');
  const [fields, setFields] = useState(null);
  const [msg, setMsg] = useState({ type: '', text: '' });
  const [formData, setFormData] = useState({});

  const extractFields = async () => {
    if(!docId) return setMsg({type:'error', text: 'Veuillez saisir un Document ID.'});
    setMsg({ type: 'info', text: 'Extraction des champs...' });
    try {
      const res = await fetchWithAuth(`/api/workflows/preparation/documents/${docId}/admin/extract-fields`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setFields(data.fields || data);
        // Préparer un objet vide pour le formulaire
        const initialForm = {};
        Object.keys(data.fields || data).forEach(k => initialForm[k] = '');
        setFormData(initialForm);
        setMsg({ type: 'success', text: 'Champs extraits.' });
      } else {
        setMsg({ type: 'error', text: 'Erreur extraction.' });
      }
    } catch (err) {
      setMsg({ type: 'error', text: 'Erreur réseau.' });
    }
  };

  const fillAdmin = async () => {
    setMsg({ type: 'info', text: 'Remplissage en cours...' });
    try {
      const res = await fetchWithAuth(`/api/workflows/preparation/documents/${docId}/admin/fill`, {
        method: 'POST',
        body: JSON.stringify({ values: formData })
      });
      if (res.ok) setMsg({ type: 'success', text: 'Document administratif généré.' });
      else setMsg({ type: 'error', text: 'Erreur remplissage.' });
    } catch (err) {
      setMsg({ type: 'error', text: 'Erreur réseau.' });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-bold text-primary">Documents Administratifs (Actes, Déclarations)</h2>
      
      {msg.text && (
        <div className={`p-3 rounded-lg text-sm font-bold ${msg.type === 'error' ? 'bg-red-500/10 text-red-600' : msg.type === 'success' ? 'bg-green-500/10 text-green-600' : 'bg-blue-500/10 text-blue-600'}`}>
          {msg.text}
        </div>
      )}

      <div className="flex gap-2">
        <input 
          type="text" 
          placeholder="UUID du Document Administratif" 
          value={docId} 
          onChange={(e) => setDocId(e.target.value)}
          className="flex-1 p-2 bg-surface-container border border-outline-variant/30 rounded-lg text-sm outline-none"
        />
        <button onClick={extractFields} className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold">Extraire</button>
      </div>

      {fields && (
        <div className="bg-surface-container-low p-4 rounded-xl border border-outline-variant/30 mt-4 flex flex-col gap-3">
          <h3 className="font-bold text-sm mb-2">Champs à remplir :</h3>
          {Object.keys(formData).map(key => (
            <div key={key} className="flex flex-col">
              <label className="text-xs font-bold uppercase text-on-surface-variant mb-1">{key}</label>
              <input 
                type="text" 
                value={formData[key]} 
                onChange={(e) => setFormData({...formData, [key]: e.target.value})}
                className="p-2 bg-surface-container border border-outline-variant/30 rounded text-sm outline-none focus:border-primary"
              />
            </div>
          ))}
          <button onClick={fillAdmin} className="mt-4 self-start bg-secondary text-on-secondary px-6 py-2 rounded-lg font-bold shadow-sm">
            Générer le Document Rempli
          </button>
        </div>
      )}
    </div>
  );
}