import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function AdminIntelligenceEngine() {
  const { fetchWithAuth } = useAuth();

  const [fewShotPrompt, setFewShotPrompt] = useState('');
  const [loadingPrompt, setLoadingPrompt] = useState(false);
  
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState(null);

  const [training, setTraining] = useState(false);
  const [trainLogs, setTrainLogs] = useState(null);
  const [trainError, setTrainError] = useState(null);

  // A. Récupérer le prompt Few-Shot
  const fetchFewShotPrompt = async () => {
    setLoadingPrompt(true);
    try {
      // Ajuste le préfixe si ces routes sont sous un routeur spécifique (ex: /classifier/learning/...)
      const res = await fetchWithAuth('/api/classifier/learning/few-shot-prompt');
      if (res.ok) {
        const data = await res.json();
        setFewShotPrompt(data.prompt_injection);
      }
    } catch (err) {
      console.error("Erreur chargement few-shot prompt:", err);
    } finally {
      setLoadingPrompt(false);
    }
  };

  useEffect(() => {
    fetchFewShotPrompt();
  }, []);

  // B. Exporter le Dataset
  const handleExportDataset = async () => {
    setExporting(true);
    setExportResult(null);
    try {
      const res = await fetchWithAuth('/api/classifier/learning/export-dataset', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setExportResult({ type: 'success', message: data.detail || 'Export réussi.' });
      } else {
        setExportResult({ type: 'error', message: data.detail || 'Erreur lors de l\'export.' });
      }
    } catch (err) {
      setExportResult({ type: 'error', message: 'Impossible de contacter le serveur.' });
    } finally {
      setExporting(false);
    }
  };

  // C. Lancer l'entraînement local
  const handleTrainLocal = async () => {
    if (!window.confirm("Attention : Le Fine-Tuning local nécessite un GPU puissant (ex: RTX 3090/4090). Voulez-vous continuer ?")) return;
    
    setTraining(true);
    setTrainLogs(null);
    setTrainError(null);
    
    try {
      const res = await fetchWithAuth('/api/classifier/learning/train-local', { method: 'POST' });
      const data = await res.json();
      
      if (res.ok) {
        setTrainLogs(data);
      } else if (res.status === 412) {
        setTrainError(`Échec matériel : ${data.detail}`);
      } else {
        setTrainError(`Erreur inattendue : ${data.detail}`);
      }
    } catch (err) {
      setTrainError('Erreur de connexion lors de la tentative de Fine-Tuning.');
    } finally {
      setTraining(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto flex flex-col gap-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-on-surface">Waraq Intelligence Engine</h1>
          <p className="text-sm text-on-surface-variant">Gestion de l'apprentissage continu et du Fine-Tuning.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Colonne Gauche : Few-Shot Prompt */}
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-sm flex flex-col h-full">
          <div className="p-4 border-b border-outline-variant/20 flex justify-between items-center bg-surface-container-low rounded-t-xl">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">code</span>
              <h3 className="font-bold text-sm text-on-surface">Contexte Few-Shot Dynamique</h3>
            </div>
            <button 
              onClick={fetchFewShotPrompt} 
              disabled={loadingPrompt}
              className="p-1.5 hover:bg-surface-container-high rounded text-on-surface-variant transition-colors"
              title="Rafraîchir"
            >
              <span className={`material-symbols-outlined text-lg ${loadingPrompt ? 'animate-spin' : ''}`}>sync</span>
            </button>
          </div>
          <div className="p-4 flex-1">
            <p className="text-xs text-on-surface-variant mb-3">
              Ce texte est généré à partir des corrections humaines récentes et sera injecté dans les requêtes IA pour améliorer la précision.
            </p>
            <div className="bg-[#1e1e1e] p-4 rounded-lg overflow-y-auto h-[350px] border border-outline-variant/10 shadow-inner font-mono text-xs text-green-400 whitespace-pre-wrap">
              {loadingPrompt ? 'Génération du contexte...' : (fewShotPrompt || 'Aucun historique de correction disponible.')}
            </div>
          </div>
        </div>

        {/* Colonne Droite : Actions d'entraînement */}
        <div className="flex flex-col gap-6">
          
          {/* Module 1 : Export Dataset */}
          <div className="bg-surface-container-lowest p-5 rounded-xl border border-outline-variant/30 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <span className="material-symbols-outlined text-secondary">download</span>
              <h3 className="font-bold text-sm text-on-surface">Export Dataset (Colab)</h3>
            </div>
            <p className="text-xs text-on-surface-variant mb-4">
              Compile l'historique validé en format <code className="bg-surface-container px-1 py-0.5 rounded">.jsonl</code> pour le Fine-Tuning externe (Google Colab).
            </p>
            
            <button 
              onClick={handleExportDataset}
              disabled={exporting}
              className="w-full flex justify-center items-center gap-2 px-4 py-2 bg-secondary text-on-secondary rounded-lg font-medium shadow-sm hover:opacity-90 disabled:opacity-50 transition-all text-sm"
            >
              <span className={`material-symbols-outlined text-lg ${exporting ? 'animate-bounce' : ''}`}>file_download</span>
              {exporting ? 'Génération en cours...' : 'Générer waraq_dataset.jsonl'}
            </button>

            {exportResult && (
              <div className={`mt-3 p-3 rounded-lg text-xs flex items-center gap-2 ${exportResult.type === 'success' ? 'bg-primary/10 text-primary border border-primary/20' : 'bg-error-container/50 text-error border border-error/20'}`}>
                <span className="material-symbols-outlined text-base">
                  {exportResult.type === 'success' ? 'check_circle' : 'error'}
                </span>
                {exportResult.message}
              </div>
            )}
          </div>

          {/* Module 2 : Fine-Tuning Local */}
          <div className="bg-surface-container-lowest p-5 rounded-xl border border-outline-variant/30 shadow-sm flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span className="material-symbols-outlined text-tertiary">memory</span>
              <h3 className="font-bold text-sm text-on-surface">Fine-Tuning Local</h3>
            </div>
            <p className="text-xs text-on-surface-variant mb-4">
              Lance le processus d'entraînement intensif directement sur la machine hôte. Requis : GPU compatible CUDA.
            </p>
            
            <button 
              onClick={handleTrainLocal}
              disabled={training}
              className="w-full flex justify-center items-center gap-2 px-4 py-2 bg-tertiary text-on-tertiary rounded-lg font-medium shadow-sm hover:opacity-90 disabled:opacity-50 transition-all text-sm"
            >
              <span className={`material-symbols-outlined text-lg ${training ? 'animate-spin' : ''}`}>model_training</span>
              {training ? 'Initialisation...' : 'Démarrer l\'entraînement'}
            </button>

            {trainError && (
              <div className="mt-3 p-3 bg-error-container/30 border border-error/30 rounded-lg text-xs flex items-start gap-2 text-error">
                <span className="material-symbols-outlined text-base mt-0.5">warning</span>
                <span>{trainError}</span>
              </div>
            )}

            {trainLogs && (
              <div className="mt-3 p-3 bg-surface-container-low border border-outline-variant/20 rounded-lg text-xs font-mono whitespace-pre-wrap max-h-[150px] overflow-y-auto">
                {JSON.stringify(trainLogs, null, 2)}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}