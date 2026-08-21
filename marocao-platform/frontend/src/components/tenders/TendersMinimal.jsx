import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function TendersMinimal() {
  const { user, fetchWithAuth } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role?.toUpperCase() === 'ADMIN';

  const [tenders, setTenders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);

  // Gestion des messages de notification internes (Remplacement des alert())
  const [notification, setNotification] = useState({ show: false, message: '', type: 'info' });

  // Filtres
  const [filters, setFilters] = useState({ reference: '', category: '', deadline: '', is_consulted: '' });

  const showNotification = (message, type = 'info') => {
    setNotification({ show: true, message, type });
    setTimeout(() => {
      setNotification({ show: false, message: '', type: 'info' });
    }, 4000);
  };

  const fetchTenders = async () => {
  setLoading(true);
  try {
    // 1. Recherche par référence
    if (filters.reference.trim() !== '') {
      const res = await fetchWithAuth('/api/tenders/search/reference', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reference: filters.reference.trim() })
      });

      if (res.ok) {
        const raw = await res.json();
        // Extrait l'objet que le backend réponde direct {...} ou {"data": {...}}
        const item = raw?.data || raw;
        setTenders(item && item.id ? [item] : []);
      } else {
        setTenders([]);
      }
      return;
    }

    // 2. Filtres standards ou liste complète
    const hasFilters = filters.category.trim() !== '' || filters.deadline !== '' || filters.is_consulted !== '';
    const url = hasFilters ? '/api/tenders/minimal/filter' : '/api/tenders/minimal';
    
    const options = hasFilters
      ? {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            category: filters.category.trim() || undefined,
            deadline: filters.deadline || undefined,
            is_consulted: filters.is_consulted !== '' ? filters.is_consulted === 'true' : undefined,
          }),
        }
      : { method: 'GET' };

    const res = await fetchWithAuth(url, options);
    if (res.ok) {
      const result = await res.json();
      setTenders(result.data || (Array.isArray(result) ? result : []));
    }
  } catch (err) {
    console.error("Erreur chargement tenders:", err);
    setTenders([]);
  } finally {
    setLoading(false);
  }
};

  useEffect(() => {
    fetchTenders();
  }, [filters]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await fetchWithAuth('/api/scraper/sync', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        showNotification(data.message || "Synchronisation terminée avec succès !", "success");
        fetchTenders();
      } else {
        showNotification("Échec de la synchronisation", "error");
      }
    } catch (err) {
      showNotification("Erreur lors de la synchronisation des données", "error");
    } finally {
      setSyncing(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetchWithAuth('/api/scraper/export-excel', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        showNotification(data.message || "Export Excel généré avec succès !", "success");
      } else {
        showNotification("Erreur lors de la génération de l'export Excel", "error");
      }
    } catch (err) {
      showNotification("Erreur d'exportation", "error");
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteSelected = async () => {
    if (!window.confirm(`Voulez-vous vraiment supprimer ${selectedIds.length} appel(s) d'offres ?`)) return;
    try {
      const res = await fetchWithAuth('/api/tenders/delete-multiple', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedIds })
      });
      if (res.ok) {
        showNotification(`${selectedIds.length} appel(s) d'offres supprimé(s)`, "success");
        setSelectedIds([]);
        fetchTenders();
      } else {
        showNotification("Erreur lors de la suppression des éléments", "error");
      }
    } catch (err) {
      showNotification("Erreur réseau lors de la suppression", "error");
    }
  };

  const toggleSelect = (id) => {
    setSelectedIds(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  const handleResetFilters = () => {
    setFilters({ reference: '', category: '', deadline: '', is_consulted: '' });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto flex flex-col gap-6">
      
      {/* Composant de Notification dynamique */}
      {notification.show && (
        <div className={`p-4 rounded-lg flex items-center justify-between shadow-md transition-all ${
          notification.type === 'success' ? 'bg-green-100 border border-green-300 text-green-800' : 
          notification.type === 'error' ? 'bg-red-100 border border-red-300 text-red-800' : 
          'bg-blue-100 border border-blue-300 text-blue-800'
        }`}>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined">
              {notification.type === 'success' ? 'check_circle' : notification.type === 'error' ? 'error' : 'info'}
            </span>
            <span className="text-sm font-semibold">{notification.message}</span>
          </div>
          <button onClick={() => setNotification({ ...notification, show: false })} className="text-xs font-bold uppercase">
            Fermer
          </button>
        </div>
      )}

      {/* En-tête & Boutons d'Action */}
      <div className="flex flex-col md:flex-row justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-on-surface">Appels d'Offres (Vue Simplifiée)</h1>
          <p className="text-sm text-on-surface-variant">Liste des marchés publics disponibles</p>
        </div>
        
        {isAdmin && (
          <div className="flex gap-2">
            <button 
              onClick={handleSync} 
              disabled={syncing} 
              className="bg-primary text-on-primary hover:bg-primary/90 px-3 py-2 rounded-lg text-sm flex items-center gap-2 transition-colors disabled:opacity-50"
            >
              <span className={`material-symbols-outlined ${syncing ? 'animate-spin' : ''}`}>sync</span>
              {syncing ? 'Synchro en cours...' : 'Sync Data'}
            </button>
            <button 
              onClick={handleExport} 
              disabled={exporting} 
              className="bg-secondary text-on-secondary hover:bg-secondary/90 px-3 py-2 rounded-lg text-sm flex items-center gap-2 transition-colors disabled:opacity-50"
            >
              <span className="material-symbols-outlined">download</span>
              {exporting ? 'Exportation...' : 'Export Excel'}
            </button>
            {selectedIds.length > 0 && (
              <button onClick={handleDeleteSelected} className="bg-error text-on-error hover:bg-error/90 px-3 py-2 rounded-lg text-sm flex items-center gap-2">
                <span className="material-symbols-outlined">delete</span>
                Supprimer ({selectedIds.length})
              </button>
            )}
          </div>
        )}
      </div>

      {/* Barre de Filtres */}
      <div className="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/30 flex flex-wrap gap-4">
        <input 
          type="text" 
          placeholder="Rechercher par Référence..." 
          value={filters.reference} 
          onChange={e => setFilters({...filters, reference: e.target.value})} 
          className="border border-outline-variant/40 rounded px-3 py-1.5 text-sm w-full md:w-1/4 font-mono" 
        />
        <input 
          type="text" 
          placeholder="Filtrer par catégorie..." 
          value={filters.category} 
          onChange={e => setFilters({...filters, category: e.target.value})} 
          className="border border-outline-variant/40 rounded px-3 py-1.5 text-sm w-full md:w-1/4" 
        />
        <input 
          type="date" 
          value={filters.deadline} 
          onChange={e => setFilters({...filters, deadline: e.target.value})} 
          className="border border-outline-variant/40 rounded px-3 py-1.5 text-sm" 
        />
        <select 
          value={filters.is_consulted} 
          onChange={e => setFilters({...filters, is_consulted: e.target.value})} 
          className="border border-outline-variant/40 rounded px-3 py-1.5 text-sm"
        >
          <option value="">Tous les statuts</option>
          <option value="true">Consultés</option>
          <option value="false">Non consultés</option>
        </select>
        <button 
        onClick={handleResetFilters}
        className="border border-outline-variant/40 rounded px-3 py-1.5 text-sm text-on-surface-variant hover:bg-surface-container-high transition-colors flex items-center gap-1"
        >
        <span className="material-symbols-outlined text-sm">restart_alt</span>
        Réinitialiser
        </button>
      </div>

      {/* Table des résultats */}
      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 overflow-hidden shadow-sm">
        <table className="w-full text-left border-collapse">
          <thead className="bg-surface-container-low text-xs uppercase text-on-surface-variant">
            <tr>
              {isAdmin && <th className="p-3 w-10"></th>}
              <th className="p-3">Référence</th>
              <th className="p-3 min-w-[300px]">Objet</th>
              <th className="p-3">Catégorie</th>
              <th className="p-3">Acheteur</th>
              <th className="p-3">Deadline</th>
              {/* <th className="p-3 text-center">Action</th> */}
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/20 text-sm">
  {loading ? (
    <tr>
      <td colSpan={isAdmin ? "6" : "5"} className="p-4 text-center">Chargement des offres...</td>
    </tr>
  ) : tenders.length === 0 ? (
    <tr>
      <td colSpan={isAdmin ? "6" : "5"} className="p-4 text-center text-on-surface-variant">
        Aucun appel d'offres trouvé.
      </td>
    </tr>
  ) : (
    tenders.map(t => (
      <tr key={t.id} className="hover:bg-surface-container-low/50 transition-colors">
        {isAdmin && (
          <td className="p-3 align-top">
            <input 
              type="checkbox" 
              checked={selectedIds.includes(t.id)} 
              onChange={() => toggleSelect(t.id)} 
              className="rounded" 
            />
          </td>
        )}
        <td className="p-3 font-mono text-xs font-bold align-top whitespace-nowrap">{t.reference}</td>
        <td className="p-3 min-w-[300px] break-words leading-relaxed align-top">{t.title}</td>
        <td className="p-3 align-top">
          <span className="bg-secondary/10 text-secondary text-xs px-2 py-0.5 rounded font-medium inline-block">
            {t.categorie || t.category || 'Non spécifiée'}
          </span>
        </td>
        <td className="p-3 align-top">{t.buyer}</td>
        
        {/* Cellule : Date + Bouton Détails (simple lien texte) côte à côte */}
<td className="p-3 text-xs whitespace-nowrap align-top">
  <div className="flex items-center gap-3">
    <span>{t.deadline || '-'}</span>
    <button 
      onClick={() => navigate(`/tenders/${t.id}`)} 
      className="text-primary hover:underline font-medium"
    >
      Détails
    </button>
  </div>
</td>
      </tr>
    ))
  )}
</tbody>
        </table>
      </div>
    </div>
  );
}