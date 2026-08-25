import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function WorkflowSignature({ tenderId }) {
  const { fetchWithAuth, user } = useAuth();
  const [signerName, setSignerName] = useState('');
  const [msg, setMsg] = useState({ type: '', text: '' });
  const [loading, setLoading] = useState(false);
  
  // Doc individuel
  const [docId, setDocId] = useState('');

  const signAll = async () => {
    if(!signerName) return setMsg({type:'error', text: 'Nom du signataire requis.'});
    setLoading(true);
    setMsg({ type: 'info', text: 'Signature globale en cours...' });
    try {
      const res = await fetchWithAuth(`/api/workflows/tenders/${tenderId}/sign`, {
        method: 'POST',
        body: JSON.stringify({ signer_name: signerName })
      });
      if (res.ok) setMsg({ type: 'success', text: 'Tous les RC/CPS ont été signés et paginés.' });
      else setMsg({ type: 'error', text: 'Erreur lors de la signature.' });
    } catch (err) {
      setMsg({ type: 'error', text: 'Erreur réseau.' });
    }
    setLoading(false);
  };

  const signIndividual = async () => {
    if(!docId || !signerName) return setMsg({type:'error', text: 'ID et Nom du signataire requis.'});
    setLoading(true);
    setMsg({ type: 'info', text: 'Signature du document...' });
    try {
      // API attend query params selon le backend (user_id: str, signer_name: str)
      const res = await fetchWithAuth(`/api/workflows/sign-document/${docId}?user_id=${user.id}&signer_name=${encodeURIComponent(signerName)}`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        setMsg({ type: 'success', text: `Document signé avec succès : ${data.output_path}` });
      } else {
        const error = await res.json();
        setMsg({ type: 'error', text: error.detail || 'Erreur lors de la signature.' });
      }
    } catch (err) {
      setMsg({ type: 'error', text: 'Erreur réseau.' });
    }
    setLoading(false);
  };

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-xl font-bold text-primary">Signature Graphique (RC / CPS)</h2>
      
      {msg.text && (
        <div className={`p-3 rounded-lg text-sm font-bold ${msg.type === 'error' ? 'bg-red-500/10 text-red-600' : msg.type === 'success' ? 'bg-green-500/10 text-green-600' : 'bg-blue-500/10 text-blue-600'}`}>
          {msg.text}
        </div>
      )}

      <div className="flex flex-col gap-2 max-w-md">
        <label className="font-bold text-sm">Nom du Signataire (qui apparaîtra sur les documents) :</label>
        <input 
          type="text" 
          value={signerName} 
          onChange={(e) => setSignerName(e.target.value)}
          className="p-2 bg-surface-container border border-outline-variant/30 rounded-lg text-sm outline-none focus:border-primary"
        />
      </div>

      <div className="p-4 bg-surface-container-low rounded-xl border border-outline-variant/30">
        <h3 className="font-bold mb-2">Option 1 : Signature Globale</h3>
        <p className="text-xs text-on-surface-variant mb-4">Signe graphiquement et pagine tous les documents RC et CPS liés à cet Appel d'Offres.</p>
        <button onClick={signAll} disabled={loading} className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold shadow-sm">
          Tout Signer
        </button>
      </div>

      <div className="p-4 bg-surface-container-low rounded-xl border border-outline-variant/30">
        <h3 className="font-bold mb-2">Option 2 : Signature Individuelle</h3>
        <input 
          type="text" 
          placeholder="UUID du Document Spécifique" 
          value={docId} 
          onChange={(e) => setDocId(e.target.value)}
          className="w-full max-w-md p-2 bg-surface-container border border-outline-variant/30 rounded-lg text-sm outline-none mb-3"
        />
        <br/>
        <button onClick={signIndividual} disabled={loading} className="bg-secondary text-on-secondary px-4 py-2 rounded-lg font-bold shadow-sm">
          Signer le document
        </button>
      </div>
    </div>
  );
}