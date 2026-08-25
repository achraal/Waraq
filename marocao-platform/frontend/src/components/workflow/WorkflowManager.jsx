import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import WorkflowPreparation from './WorkflowPreparation';
import WorkflowValidation from './WorkflowValidation';
import WorkflowBDP from './WorkflowBDP';
import WorkflowAdmin from './WorkflowAdmin';
import WorkflowSignature from './WorkflowSignature';
import WorkflowFinalization from './WorkflowFinalization';

export default function WorkflowManager() {
  const { user } = useAuth();
  const [tenderId, setTenderId] = useState('');
  const [activeTab, setActiveTab] = useState('preparation');

  const tabs = [
    { id: 'preparation', label: '1. Préparation' },
    { id: 'validation', label: '2. Validation' },
    { id: 'bdp', label: '3. BDP' },
    { id: 'admin', label: '4. Actes / Admin' },
    { id: 'signature', label: '5. Signature' },
    { id: 'finalization', label: '6. Finalisation' }
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold">Génération du Dossier d'Appel d'Offres</h1>
        <p className="text-sm text-on-surface-variant">Automatisation, extraction, remplissage et signature du dossier.</p>
      </div>

      <div className="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/30 shadow-sm flex gap-4 items-center">
        <label className="font-bold text-sm">UUID de l'Appel d'Offres :</label>
        <input 
          type="text" 
          placeholder="Ex: 123e4567-e89b-12d3-a456-426614174000" 
          value={tenderId} 
          onChange={(e) => setTenderId(e.target.value)}
          className="flex-1 p-2 bg-surface-container border border-outline-variant/30 rounded-lg text-sm outline-none focus:border-primary"
        />
      </div>

      {tenderId ? (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-sm overflow-hidden flex flex-col">
          <div className="flex border-b border-outline-variant/30 bg-surface-container-low overflow-x-auto">
            {tabs.map(tab => (
              <button 
                key={tab.id}
                onClick={() => setActiveTab(tab.id)} 
                className={`px-4 py-3 font-bold text-sm whitespace-nowrap ${activeTab === tab.id ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:bg-surface-container-high'}`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="p-6">
            {activeTab === 'preparation' && <WorkflowPreparation tenderId={tenderId} />}
            {activeTab === 'validation' && <WorkflowValidation tenderId={tenderId} />}
            {activeTab === 'bdp' && <WorkflowBDP tenderId={tenderId} />}
            {activeTab === 'admin' && <WorkflowAdmin tenderId={tenderId} />}
            {activeTab === 'signature' && <WorkflowSignature tenderId={tenderId} />}
            {activeTab === 'finalization' && <WorkflowFinalization tenderId={tenderId} />}
          </div>
        </div>
      ) : (
        <div className="text-center p-10 bg-surface-container-lowest rounded-xl border border-outline-variant/30 text-on-surface-variant">
          Veuillez renseigner un UUID d'Appel d'Offres pour commencer.
        </div>
      )}
    </div>
  );
}