import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function DocumentValidator() {
  const { tenderId, documentId } = useParams();
  const navigate = useNavigate();
  const { fetchWithAuth } = useAuth();
  
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  
  // Modes: 'VALIDATE', 'CORRECT', 'SPLIT', 'UNDO'
  const [mode, setMode] = useState('VALIDATE');
  const [correctedType, setCorrectedType] = useState('');
  const [splits, setSplits] = useState([{ start_page: 1, end_page: 1, file_type: '' }]);

  const [notification, setNotification] = useState({ show: false, message: '', type: '' });

  const showMessage = (msg, type = 'info') => {
    setNotification({ show: true, message: msg, type });
    // Masque le message après 3 secondes s'il n'y a pas de redirection
    setTimeout(() => setNotification({ show: false, message: '', type: '' }), 3000);
  };

  const documentTypesList = ["RC", "CPS", "CCAG", "BORDEREAU", "AVIS", "DOCUMENT_UNIQUE", "ANNEXE"];

  useEffect(() => {
    const fetchDoc = async () => {
      try {
        // Adapt to your actual endpoint to get a single document's info
        const res = await fetchWithAuth(`/api/tenders/${tenderId}`);
        const data = await res.json();
        const found = data.documents?.find(d => d.id === documentId);
        setDoc(found);
        if (found) setCorrectedType(found.file_type || '');
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchDoc();
  }, [documentId, tenderId]);

  const handleAddSplit = () => {
    setSplits([...splits, { start_page: 1, end_page: 1, file_type: '' }]);
  };

  const handleSplitChange = (index, field, value) => {
    const newSplits = [...splits];
    newSplits[index][field] = field.includes('page') ? parseInt(value) || 1 : value;
    setSplits(newSplits);
  };

  const handleRemoveSplit = (index) => {
    setSplits(splits.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    
    // Construction du payload selon ton endpoint FastAPI
    const payload = {
      is_correct: mode === 'VALIDATE',
      corrected_type: mode === 'CORRECT' ? correctedType : null,
      undo_split: mode === 'UNDO',
      is_split_required: mode === 'SPLIT',
      splits: mode === 'SPLIT' ? splits : null
    };

    // REMPLACER ton try/catch dans handleSubmit par ceci :
    try {
      const res = await fetchWithAuth(`/api/classifier/documents/${documentId}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const result = await res.json();
      if (res.ok) {
        showMessage("Validation enregistrée avec succès !", "success");
        // Redirection après 1.5 secondes
        setTimeout(() => navigate(`/tenders/${tenderId}/classifier`), 1500); 
      } else {
        showMessage(`Erreur: ${result.detail}`, "error");
      }
    } catch (err) {
      showMessage("Erreur de connexion au serveur.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="p-10 text-center">Chargement du document...</div>;
  if (!doc) return <div className="p-10 text-center text-error">Document introuvable.</div>;

  return (
    <div className="flex h-screen bg-surface overflow-hidden">
      
      {/* Zone Gauche : Visionneuse PDF */}
      <div className="flex-1 border-r border-outline-variant/30 flex flex-col relative bg-surface-container-lowest">
        <div className="p-3 bg-surface-container-low border-b border-outline-variant/20 flex items-center justify-between">
          <div className="truncate font-mono text-sm max-w-xl">{doc.file_name}</div>
          <a href={`http://localhost:8000/api/classifier/documents/${doc.id}/view`} target="_blank" rel="noreferrer" className="text-primary text-xs font-bold flex items-center gap-1">
            <span className="material-symbols-outlined text-sm">open_in_new</span> Plein écran
          </a>
        </div>
        <iframe 
          src={`http://localhost:8000/api/classifier/documents/${doc.id}/view`} 
          className="w-full h-full border-none"
          title="Document Viewer"
        />
      </div>

      {/* Zone Droite : Outils de Validation */}
      <div className="w-96 flex flex-col bg-surface overflow-y-auto">
        <div className="p-4 border-b border-outline-variant/20">
          <button onClick={() => navigate(`/tenders/${tenderId}/classify`)} className="text-sm flex items-center gap-1 text-on-surface-variant hover:text-primary mb-4">
            <span className="material-symbols-outlined text-sm">arrow_back</span> Retour
          </button>
          <h2 className="text-xl font-bold">Validation Humaine</h2>
          <div className="mt-2 text-sm p-3 bg-surface-container rounded-lg">
            <span className="block text-on-surface-variant">Prédiction IA :</span>
            <span className="font-bold text-secondary text-lg">{doc.file_type || "Non classifié"}</span>
          </div>
        </div>

        <div className="p-4 flex flex-col gap-4">
            {notification.show && (
            <div className={`p-3 rounded-lg flex items-start gap-2 shadow-sm text-sm font-medium ${
              notification.type === 'error' ? 'bg-error/10 text-error border border-error/20' : 'bg-primary/10 text-primary border border-primary/20'
            }`}>
              <span className="material-symbols-outlined text-[20px]">
                {notification.type === 'error' ? 'error' : 'check_circle'}
              </span>
              <span>{notification.message}</span>
            </div>
          )}
          <h3 className="font-bold text-sm uppercase text-on-surface-variant">Action à effectuer</h3>

          
          {/* Nouveau sélecteur de mode avec icônes Material */}
          <div className="flex flex-col gap-2">
            {[
              { id: 'VALIDATE', icon: 'check_circle', label: 'Confirmer la prédiction' },
              { id: 'CORRECT', icon: 'edit', label: 'Corriger le type de document' },
              { id: 'SPLIT', icon: 'content_cut', label: 'Découper manuellement' },
              { id: 'UNDO', icon: 'undo', label: 'Annuler un découpage IA précédent' }
            ].map(opt => (
              <button
                key={opt.id}
                onClick={() => setMode(opt.id)}
                className={`flex items-center gap-3 p-3 rounded-lg border text-left transition-colors ${
                  mode === opt.id 
                    ? 'bg-primary/10 border-primary text-primary font-bold shadow-sm' 
                    : 'bg-surface-container-lowest border-outline-variant/50 hover:bg-surface-container text-on-surface'
                }`}
              >
                <span className="material-symbols-outlined">{opt.icon}</span>
                <span className="text-sm">{opt.label}</span>
              </button>
            ))}
          </div>

          {/* Formulaire Dynamique selon le Mode */}
          <div className="mt-2 bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/30">
            
            {mode === 'VALIDATE' && (
              <p className="text-sm text-on-surface-variant">Confirmez que ce document est bien un <b>{doc.file_type}</b> complet.</p>
            )}

            {mode === 'CORRECT' && (
              <div className="flex flex-col gap-2">
                <label className="text-sm font-bold">Nouveau type :</label>
                <select 
                  value={correctedType} 
                  onChange={(e) => setCorrectedType(e.target.value)}
                  className="p-2 border border-outline-variant rounded-lg"
                >
                  <option value="">Sélectionner...</option>
                  {documentTypesList.map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>
            )}

            {mode === 'SPLIT' && (
              <div className="flex flex-col gap-4">
                <p className="text-xs text-on-surface-variant">Définissez les intervalles de pages pour extraire de nouveaux documents.</p>
                {splits.map((split, idx) => (
                  <div key={idx} className="flex flex-col gap-2 p-3 border border-outline-variant/40 rounded bg-surface-container">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-bold">Extrait #{idx + 1}</span>
                      <button onClick={() => handleRemoveSplit(idx)} className="text-error text-xs hover:underline">Supprimer</button>
                    </div>
                    <div className="flex gap-2">
                      <input type="number" min="1" value={split.start_page} onChange={(e) => handleSplitChange(idx, 'start_page', e.target.value)} className="w-16 p-1 border rounded text-sm" placeholder="De" />
                      <span className="self-center text-sm">à</span>
                      <input type="number" min="1" value={split.end_page} onChange={(e) => handleSplitChange(idx, 'end_page', e.target.value)} className="w-16 p-1 border rounded text-sm" placeholder="À" />
                    </div>
                    <select value={split.file_type} onChange={(e) => handleSplitChange(idx, 'file_type', e.target.value)} className="w-full p-1 border rounded text-sm mt-1">
                      <option value="">Type de l'extrait...</option>
                      {documentTypesList.map(type => <option key={type} value={type}>{type}</option>)}
                    </select>
                  </div>
                ))}
                <button onClick={handleAddSplit} className="text-sm text-primary flex items-center gap-1 hover:underline">
                  <span className="material-symbols-outlined text-sm">add_circle</span> Ajouter un extrait
                </button>
              </div>
            )}

            {mode === 'UNDO' && (
              <p className="text-sm text-error font-medium">Attention : Cela supprimera tous les documents enfants générés pour retrouver le fichier d'origine unique.</p>
            )}

          </div>

          <button 
            onClick={handleSubmit} 
            disabled={submitting}
            className="mt-6 w-full py-3 bg-primary text-on-primary rounded-lg font-bold hover:bg-primary/90 disabled:opacity-50 transition flex justify-center items-center gap-2"
          >
            {submitting ? 'Enregistrement...' : 'Valider et Sauvegarder'}
            {!submitting && <span className="material-symbols-outlined text-sm">save</span>}
          </button>
        </div>
      </div>
    </div>
  );
}