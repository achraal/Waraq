import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function TendersFullList() {
  const { fetchWithAuth } = useAuth();
  const navigate = useNavigate();

  const [tenders, setTenders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
  category: '',
  deadline: '',
  extraction_date: '',
  is_consulted: '' 
});

  const fetchFullTenders = async () => {
  setLoading(true);
  try {
    // Construction dynamique du body avec uniquement les filtres renseignés
    const payload = {};
    if (filters.category) payload.category = filters.category;
    if (filters.deadline) payload.deadline = filters.deadline;
    if (filters.extraction_date) payload.extraction_date = filters.extraction_date;
    if (filters.is_consulted !== '') payload.is_consulted = filters.is_consulted === 'true';

    const hasFilters = Object.keys(payload).length > 0;
    const url = hasFilters ? '/api/tenders/filter' : '/api/tenders/';
    const options = hasFilters 
      ? { method: 'POST', body: JSON.stringify(payload) } 
      : { method: 'GET' };

    const res = await fetchWithAuth(url, options);
    if (res.ok) {
      const data = await res.json();
      setTenders(data.data || []);
    }
  } catch (err) {
    console.error(err);
  } finally {
    setLoading(false);
  }
};

  useEffect(() => {
    fetchFullTenders();
  }, [filters]);

  return (
    <div className="p-6 max-w-7xl mx-auto flex flex-col gap-6">
      {/* Header & Recherche */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-on-surface">Base de Données Complète (Tenders)</h1>
          <p className="text-sm text-on-surface-variant">Affichage exhaustif de toutes les métadonnées extraites.</p>
        </div>
        <div className="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/30 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
  {/* Catégorie */}
  <input 
    type="text" 
    placeholder="Catégorie (ex: Travaux)..." 
    value={filters.category} 
    onChange={e => setFilters(prev => ({ ...prev, category: e.target.value }))} 
    className="border border-outline-variant/40 bg-transparent rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50" 
  />

  {/* Date Limite */}
  <input 
    type="text" 
    placeholder="Date limite (ex: 2026-09)..." 
    value={filters.deadline} 
    onChange={e => setFilters(prev => ({ ...prev, deadline: e.target.value }))} 
    className="border border-outline-variant/40 bg-transparent rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50" 
  />

  {/* Date d'extraction */}
  <input 
    type="date" 
    value={filters.extraction_date} 
    onChange={e => setFilters(prev => ({ ...prev, extraction_date: e.target.value }))} 
    className="border border-outline-variant/40 bg-transparent rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/50" 
  />

  {/* Statut Consulté */}
  <select 
    value={filters.is_consulted} 
    onChange={e => setFilters(prev => ({ ...prev, is_consulted: e.target.value }))} 
    className="border border-outline-variant/40 bg-surface-container-lowest text-on-surface rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
  >
    <option value="">Tous les statuts</option>
    <option value="true">Consulté</option>
    <option value="false">Non consulté</option>
  </select>
</div>
      </div>

      {/* Liste complète des cartes */}
      {loading ? (
        <div className="p-12 text-center text-on-surface-variant font-medium">
          Chargement des données complètes...
        </div>
      ) : tenders.length === 0 ? (
        <div className="p-12 text-center text-on-surface-variant bg-surface-container-lowest rounded-xl border border-outline-variant/30">
          Aucun appel d'offres trouvé.
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {tenders.map(t => (
            <div 
              key={t.id} 
              className="bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-6 shadow-sm flex flex-col gap-5"
            >
              {/* En-tête de la carte */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-outline-variant/20 pb-4">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-3 py-1 rounded-md">
                    {t.reference}
                  </span>
                  <span className="text-xs text-on-surface-variant font-mono">ID: {t.id}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold px-2.5 py-1 rounded-md ${
                    t.scraping_status === 'COMPLETED' 
                      ? 'bg-emerald-500/10 text-emerald-600' 
                      : 'bg-surface-variant text-on-surface-variant'
                  }`}>
                    RAG: {t.scraping_status}
                  </span>
                  {t.is_consulted && (
                    <span className="text-xs bg-blue-500/10 text-blue-600 px-2.5 py-1 rounded-md font-medium">
                      Consulté
                    </span>
                  )}
                  {t.is_zip_corrupted && (
                    <span className="text-xs bg-red-500/10 text-red-600 px-2.5 py-1 rounded-md font-medium">
                      ZIP Corrompu
                    </span>
                  )}
                </div>
              </div>

              {/* Titre & Acheteur */}
              <div>
                <h2 className="text-lg font-bold text-on-surface mb-1">{t.title}</h2>
                <p className="text-sm font-medium text-on-surface-variant">Acheteur : <span className="text-on-surface">{t.buyer || "N/A"}</span></p>
              </div>

              {/* Section 1 : Informations Générales */}
              <div className="bg-surface-container-low/40 p-4 rounded-lg border border-outline-variant/20">
                <h3 className="text-xs font-bold uppercase text-on-surface-variant mb-3">Informations Générales</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
                  <div>
                    <span className="text-on-surface-variant block font-medium">Type d'annonce</span>
                    <span className="text-on-surface">{t.type_annonce || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Procédure</span>
                    <span className="text-on-surface">{t.procedure || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Catégorie</span>
                    <span className="text-on-surface">{t.categorie || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Domaines d'activité</span>
                    <span className="text-on-surface">{t.domaines_activite || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Allotissement</span>
                    <span className="text-on-surface">{t.allotissement || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Lieu d'exécution</span>
                    <span className="text-on-surface">{t.lieu_execution || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Réservé PME</span>
                    <span className="text-on-surface">{t.reserve_pme || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Variante</span>
                    <span className="text-on-surface">{t.variante || "N/A"}</span>
                  </div>
                </div>
              </div>

              {/* Section 2 : Exigences & Finances */}
              <div className="bg-surface-container-low/40 p-4 rounded-lg border border-outline-variant/20">
                <h3 className="text-xs font-bold uppercase text-on-surface-variant mb-3">Conditions Financières & Qualifications</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
                  <div>
                    <span className="text-on-surface-variant block font-medium">Budget Estimé</span>
                    <span className="text-on-surface font-semibold">{t.estimated_budget || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Caution Provisoire</span>
                    <span className="text-on-surface font-semibold">{t.provisional_caution || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Prix d'acquisition</span>
                    <span className="text-on-surface">{t.prix_acquisition || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Qualifications</span>
                    <span className="text-on-surface">{t.qualifications || "N/A"}</span>
                  </div>
                  <div className="md:col-span-2">
                    <span className="text-on-surface-variant block font-medium">Agréments</span>
                    <span className="text-on-surface">{t.agrements || "N/A"}</span>
                  </div>
                  <div className="md:col-span-2">
                    <span className="text-on-surface-variant block font-medium">Prospectus & Notices</span>
                    <span className="text-on-surface">{t.prospectus_notices || "N/A"}</span>
                  </div>
                </div>
              </div>

              {/* Section 3 : Adresses, Réunion & Contacts */}
              <div className="bg-surface-container-low/40 p-4 rounded-lg border border-outline-variant/20">
                <h3 className="text-xs font-bold uppercase text-on-surface-variant mb-3">Lieux, Réunions & Contacts</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
                  <div>
                    <span className="text-on-surface-variant block font-medium">Adresse de Retrait</span>
                    <span className="text-on-surface">{t.adresse_retrait || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Adresse de Dépôt</span>
                    <span className="text-on-surface">{t.adresse_depot || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Lieu d'Ouverture</span>
                    <span className="text-on-surface">{t.lieu_ouverture || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Réunion</span>
                    <span className="text-on-surface">{t.reunion || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Visite des Lieux</span>
                    <span className="text-on-surface">{t.visite_lieux || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-medium">Contact Administratif</span>
                    <span className="text-on-surface">{t.contact_administratif || "N/A"}</span>
                  </div>
                </div>
              </div>

              {/* Section 4 : Métriques Système & Métadonnées */}
              <div className="bg-surface-container-low/40 p-4 rounded-lg border border-outline-variant/20">
                <h3 className="text-xs font-bold uppercase text-on-surface-variant mb-3">Métriques Système & Extractions</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 text-xs font-mono">
                  <div>
                    <span className="text-on-surface-variant block font-sans">Date Limite</span>
                    <span className="text-on-surface font-semibold">{t.deadline || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-sans">Nombre de Lots</span>
                    <span className="text-on-surface">{t.nbr_lots ?? t.lots?.length ?? 0}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-sans">Nombre de Docs</span>
                    <span className="text-on-surface">{t.nbr_documents ?? t.documents?.length ?? 0}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-sans">Date Extraction</span>
                    <span className="text-on-surface">
                      {t.extraction_date ? new Date(t.extraction_date).toLocaleString('fr-FR') : "N/A"}
                    </span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-sans">Créé le</span>
                    <span className="text-on-surface">
                      {t.created_at ? new Date(t.created_at).toLocaleString('fr-FR') : "N/A"}
                    </span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-sans">Durée Scraping</span>
                    <span className="text-on-surface">
                      {t.scraping_duration_sec ? `${t.scraping_duration_sec}s` : "N/A"}
                    </span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block font-sans">Récursif</span>
                    <span className="text-on-surface">{t.is_recursive ? "Oui" : "Non"}</span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-on-surface-variant block font-sans">Chemin ZIP Local</span>
                    <span className="text-on-surface truncate block" title={t.local_zip_path}>
                      {t.local_zip_path || "N/A"}
                    </span>
                  </div>
                </div>

                {/* Message d'erreur s'il existe */}
                {t.scraping_error_message && (
                  <div className="mt-3 p-2.5 bg-red-500/10 text-red-600 rounded text-xs">
                    <strong>Erreur Scraping :</strong> {t.scraping_error_message}
                  </div>
                )}
              </div>

              {/* Pied de Carte & Action */}
              <div className="flex justify-end pt-2">
                <button 
                  onClick={() => navigate(`/tenders/${t.id}`)} 
                  className="bg-primary hover:bg-primary/90 text-on-primary px-5 py-2 rounded-lg font-medium text-xs transition-colors"
                >
                  Ouvrir l'Appel d'Offres
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}