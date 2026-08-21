import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function TenderDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, fetchWithAuth } = useAuth();
  const isAdmin = user?.role?.toUpperCase() === 'ADMIN';

  const [tender, setTender] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [formData, setFormData] = useState({});

  const fetchTenderDetail = async () => {
    try {
      const res = await fetchWithAuth(`/api/tenders/${id}`);
      if (res.ok) {
        const data = await res.json();
        setTender(data);
        setFormData(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenderDetail();
  }, [id]);

  const handleUpdate = async (e) => {
    e.preventDefault();
    try {
      const res = await fetchWithAuth(`/api/tenders/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      if (res.ok) {
        setEditing(false);
        fetchTenderDetail();
      }
    } catch (err) {
      alert("Erreur lors de la mise à jour");
    }
  };

  const toggleConsulted = async () => {
    const endpoint = tender.is_consulted ? `/api/tenders/${id}/mark-unconsulted` : `/api/tenders/${id}/mark-consulted`;
    try {
      const res = await fetchWithAuth(endpoint, { method: 'PATCH' });
      if (res.ok) fetchTenderDetail();
    } catch (err) {
      console.error(err);
    }
  };

  const formatValue = (val) => {
    if (val === null || val === undefined || val === '') return <span className="text-on-surface-variant/40 italic">Non renseigné</span>;
    if (typeof val === 'boolean') return val ? <span className="text-green-600 font-bold">Oui</span> : <span className="text-red-500 font-bold">Non</span>;
    if (typeof val === 'object') return <pre className="text-[10px] bg-slate-900 text-green-400 p-2 rounded overflow-x-auto">{JSON.stringify(val, null, 2)}</pre>;
    return String(val);
  };

  if (loading) return <div className="p-10 text-center font-medium">Chargement des détails complets...</div>;
  if (!tender) return <div className="p-10 text-center text-error font-semibold">Appel d'offres introuvable.</div>;

  const getScrapingStatusBadge = (status) => {
  switch (status) {
    case 'SUCCESS':
    case 'COMPLETED':
      return 'bg-green-600';
    case 'PENDING':
    case 'IN_PROGRESS':
      return 'bg-blue-600';
    case 'SELENIUM_ERROR':
    case 'DOWNLOAD_ERROR':
      return 'bg-red-600';
    default:
      return 'bg-amber-600';
  }
};

  return (
    <div className="p-6 max-w-[1600px] mx-auto flex flex-col gap-6 text-on-surface">
      {/* Barre d'actions & En-tête */}
      <div className="flex items-center justify-between">
        <button onClick={() => navigate('/tenders')} className="text-sm flex items-center gap-1 text-on-surface-variant hover:text-primary transition-colors">
          <span className="material-symbols-outlined text-sm">arrow_back</span> Retour
        </button>
        <div className="flex gap-2">
          <button 
      onClick={() => navigate(`/tenders/${id}/classifier`)} 
      className="px-3 py-1.5 bg-surface-container border border-outline-variant/30 rounded-lg text-sm flex items-center gap-2 hover:bg-surface-container-high font-medium text-primary"
    >
      <span className="material-symbols-outlined text-[18px]">auto_awesome</span>
      Gérer l'IA des Documents
    </button>
          {isAdmin && (
            <button onClick={() => setEditing(!editing)} className="px-4 py-2 bg-surface-container border border-outline-variant/30 rounded-lg text-sm font-semibold hover:bg-surface-container-high">
              {editing ? 'Annuler l\'édition' : 'Modifier les métadonnées'}
            </button>
          )}
          <button onClick={toggleConsulted} className={`px-4 py-2 rounded-lg text-sm font-semibold text-white transition-colors ${tender.is_consulted ? 'bg-secondary hover:bg-secondary/90' : 'bg-primary hover:bg-primary/90'}`}>
            {tender.is_consulted ? 'Marquer Non Consulté' : 'Marquer Consulté'}
          </button>
        </div>
      </div>

      {/* Formulaire d'édition pour Administrateur */}
      {editing ? (
        <form onSubmit={handleUpdate} className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/30 flex flex-col gap-6 shadow-sm">
          <h2 className="font-bold text-xl text-primary">Édition Complète des Métadonnées</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.keys(formData).map((key) => {
              if (['id', 'lots', 'documents', 'created_at', 'metadata_json', 'administrative_zones', 'analysis_metadata'].includes(key)) return null;
              return (
                <div key={key} className="flex flex-col gap-1">
                  <label className="text-xs font-semibold text-on-surface-variant uppercase">{key.replace('_', ' ')}</label>
                  <input
                    type="text"
                    value={formData[key] !== null ? formData[key] : ''}
                    onChange={e => setFormData({ ...formData, [key]: e.target.value })}
                    className="border border-outline-variant/40 rounded p-2 text-sm bg-surface-container-lowest focus:outline-primary"
                  />
                </div>
              );
            })}
          </div>
          <button type="submit" className="bg-primary text-white py-2.5 rounded-lg self-end px-8 font-semibold shadow hover:bg-primary/90">
            Enregistrer les modifications
          </button>
        </form>
      ) : (
        <>
          {/* Section 1 : Métadonnées Générales de l'Appel d'Offres */}
          <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/30 shadow-sm flex flex-col gap-6">
            <div className="flex flex-col md:flex-row justify-between items-start gap-4 border-b pb-4">
              <div>
                <div className="flex flex-wrap gap-2 items-center mb-2">
                  <span className="text-xs bg-primary/10 text-primary border border-primary/20 px-2.5 py-1 rounded-full font-bold">{tender.reference}</span>
                  {tender.type_annonce && <span className="text-xs bg-secondary/10 text-secondary px-2.5 py-1 rounded-full font-medium">{tender.type_annonce}</span>}
                  <span className={`text-xs px-2.5 py-1 rounded-full text-white font-semibold ${getScrapingStatusBadge(tender.scraping_status)}`}>
                    Scraping: {tender.scraping_status}
                  </span>
                  <span className="text-xs bg-surface-container-high border px-2 py-1 rounded">UUID: {tender.id}</span>
                </div>
                <h1 className="text-2xl font-bold text-on-surface">{tender.title}</h1>
                <p className="text-base font-semibold text-on-surface-variant mt-1">Acheteur: {tender.buyer}</p>
              </div>
              <div className="text-right text-sm bg-surface-container-low p-3 rounded-lg border border-outline-variant/20 min-w-[220px]">
                <p className="font-bold">Deadline: <span className="text-error">{tender.deadline || 'Non précisée'}</span></p>
                <p className="font-bold mt-1">Budget Estimé: <span className="text-primary">{tender.estimated_budget || 'N/A'}</span></p>
                <p className="text-xs text-on-surface-variant mt-1">Extraction: {tender.extraction_date ? new Date(tender.extraction_date).toLocaleString() : 'N/A'}</p>
                <p className="text-xs text-on-surface-variant">Créé le: {tender.created_at ? new Date(tender.created_at).toLocaleString() : 'N/A'}</p>
              </div>
            </div>

            {/* Grille exhaustive des métadonnées administrative marocaines */}
            <h3 className="font-bold text-md text-primary">Caractéristique & Procédures</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm bg-surface-container-low/40 p-4 rounded-lg border border-outline-variant/20">
              <div><span className="font-semibold block text-xs text-on-surface-variant">Catégorie</span>{formatValue(tender.categorie)}</div>
              <div><span className="font-semibold block text-xs text-on-surface-variant">Procédure</span>{formatValue(tender.procedure)}</div>
              <div><span className="font-semibold block text-xs text-on-surface-variant">Lieu d'exécution</span>{formatValue(tender.lieu_execution)}</div>
              <div><span className="font-semibold block text-xs text-on-surface-variant">Caution Provisoire</span>{formatValue(tender.provisional_caution)}</div>
              <div><span className="font-semibold block text-xs text-on-surface-variant">Réservé PME</span>{formatValue(tender.reserve_pme)}</div>
              <div><span className="font-semibold block text-xs text-on-surface-variant">Prix d'acquisition</span>{formatValue(tender.prix_acquisition)}</div>
              <div><span className="font-semibold block text-xs text-on-surface-variant">Variante</span>{formatValue(tender.variante)}</div>
              <div><span className="font-semibold block text-xs text-on-surface-variant">Allotissement</span>{formatValue(tender.allotissement)}</div>
              <div><span className="font-semibold block text-xs text-on-surface-variant">Nombre de Lots</span><span className="font-bold">{tender.nbr_lots}</span></div>
              <div><span className="font-semibold block text-xs text-on-surface-variant">Nombre de Documents</span><span className="font-bold">{tender.nbr_documents}</span></div>
              <div><span className="font-semibold block text-xs text-on-surface-variant">Domaines d'activité</span>{formatValue(tender.domaines_activite)}</div>
              <div><span className="font-semibold block text-xs text-on-surface-variant">Contact Administratif</span>{formatValue(tender.contact_administratif)}</div>
              <div><span className="font-semibold block text-xs text-on-surface-variant">Qualifications requises</span>{formatValue(tender.qualifications)}</div>
              <div className="col-span-1 md:col-span-3"><span className="font-semibold block text-xs text-on-surface-variant">Agréments requis</span>{formatValue(tender.agrements)}</div>
            </div>

            {/* Logistique, Adresses & RDV */}
            <h3 className="font-bold text-md text-primary mt-2">Logistique, Adresses & Rendez-vous</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs bg-surface-container-low p-4 rounded-lg border border-outline-variant/20">
              <div><span className="font-bold block mb-1">Adresse de Retrait:</span>{formatValue(tender.adresse_retrait)}</div>
              <div><span className="font-bold block mb-1">Adresse de Dépôt:</span>{formatValue(tender.adresse_depot)}</div>
              <div><span className="font-bold block mb-1">Lieu d'Ouverture des Plis:</span>{formatValue(tender.lieu_ouverture)}</div>
              <div><span className="font-bold block mb-1">Détails Réunion:</span>{formatValue(tender.reunion)}</div>
              <div><span className="font-bold block mb-1">Visite des Lieux:</span>{formatValue(tender.visite_lieux)}</div>
              <div><span className="font-bold block mb-1">Prospectus & Notices:</span>{formatValue(tender.prospectus_notices)}</div>
            </div>

            {/* Système, Scraping & Métriques */}
<h3 className="font-bold text-md text-primary mt-2">Métriques Moteur & Scraping</h3>
<div className="bg-surface-container-high/30 p-4 rounded-lg border border-outline-variant/20 font-mono text-xs flex flex-col gap-4">
  
  {/* Chemin ZIP sur toute la largeur avec retour à la ligne automatique */}
  <div className="w-full border-b border-outline-variant/10 pb-3">
    <span className="font-bold block text-on-surface-variant mb-1">Chemin ZIP Local:</span>
    <div className="break-all bg-surface-container-low p-2 rounded border border-outline-variant/10">
      {formatValue(tender.local_zip_path)}
    </div>
  </div>

  {/* Les 3 autres métriques alignées en grille */}
  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
    <div>
      <span className="font-bold block text-on-surface-variant">Durée Scraping (sec):</span>
      {formatValue(tender.scraping_duration_sec)}
    </div>
    <div>
      <span className="font-bold block text-on-surface-variant">ZIP Corrompu:</span>
      {formatValue(tender.is_zip_corrupted)}
    </div>
    <div>
      <span className="font-bold block text-on-surface-variant">Mode Récursif:</span>
      {formatValue(tender.is_recursive)}
    </div>
  </div>

  {/* Message d'erreur si présent */}
  {tender.scraping_error_message && (
    <div className="text-red-600 bg-red-50 p-2 rounded border border-red-200">
      <span className="font-bold block">Erreur Scraping:</span>
      {tender.scraping_error_message}
    </div>
  )}
</div>

            {/* Metadata JSON Brute */}
            {tender.metadata_json && (
              <details className="mt-2 text-xs">
                <summary className="cursor-pointer font-bold text-on-surface-variant hover:text-primary">Voir Metadata JSON brute</summary>
                <pre className="mt-2 p-3 bg-slate-900 text-green-400 rounded-lg overflow-x-auto text-[11px] font-mono">
                  {JSON.stringify(tender.metadata_json, null, 2)}
                </pre>
              </details>
            )}
          </div>

          {/* Section 2 : Détails Exhaustifs des Lots */}
          <div className="flex flex-col gap-4">
            <h3 className="font-bold text-xl text-primary">Lots ({tender.lots?.length || 0})</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {tender.lots?.map((lot) => (
                <div key={lot.id} className="bg-surface-container-lowest p-5 rounded-xl border border-outline-variant/30 flex flex-col gap-3 shadow-sm">
                  <div className="flex justify-between items-start border-b pb-2">
                    <div>
                      <span className="text-xs font-bold font-mono bg-primary/10 text-primary px-2 py-0.5 rounded">N° {lot.lot_number || 'Non spécifié'}</span>
                      <h4 className="font-bold text-base mt-1">{lot.title || 'Lot sans titre'}</h4>
                    </div>
                    {lot.estimated_budget && <span className="text-xs font-mono font-bold bg-green-100 text-green-800 px-2 py-1 rounded">{lot.estimated_budget}</span>}
                  </div>
                  
                  <p className="text-xs text-on-surface-variant leading-relaxed">{lot.description || 'Aucune description disponible'}</p>

                  <div className="grid grid-cols-2 gap-2 text-xs bg-surface-container-low p-3 rounded-lg border border-outline-variant/20 mt-1">
                    <div><span className="font-semibold block text-on-surface-variant">Caution Provisoire:</span> {formatValue(lot.provisional_caution)}</div>
                    <div><span className="font-semibold block text-on-surface-variant">Variante:</span> {formatValue(lot.variante)}</div>
                    <div><span className="font-semibold block text-on-surface-variant">Réservé PME:</span> {formatValue(lot.reserve_pme)}</div>
                    <div><span className="font-semibold block text-on-surface-variant">Qualif. Exigées:</span> {formatValue(lot.qualifications)}</div>
                    <div><span className="font-semibold block text-on-surface-variant">Agréments Exigés:</span> {formatValue(lot.agrements)}</div>
                    <div><span className="font-semibold block text-on-surface-variant">Considérations Env.:</span> {formatValue(lot.env_considerations)}</div>
                    <div><span className="font-semibold block text-on-surface-variant">Prospectus / Notices:</span> {formatValue(lot.prospectus_notices)}</div>
                    <div><span className="font-semibold block text-on-surface-variant">Réunion:</span> {formatValue(lot.reunion)}</div>
                    <div className="col-span-2"><span className="font-semibold block text-on-surface-variant">Visite des lieux:</span> {formatValue(lot.visite_lieux)}</div>
                  </div>
                  <div className="text-[10px] font-mono text-on-surface-variant/60">ID Lot: {lot.id} | Tender ID: {lot.tender_id}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Section 3 : Tous les Documents et Métriques IA / OCR / RAG (Layout en Cartes) */}
<div className="flex flex-col gap-4">
  <div className="flex justify-between items-center">
    <h3 className="font-bold text-xl text-primary">
      Documents Associés & Pipeline IA ({tender.documents?.length || 0})
    </h3>
  </div>

  <div className="grid grid-cols-1 gap-4">
    {tender.documents?.map((doc) => (
      <div 
        key={doc.id} 
        className="bg-surface-container-lowest p-5 rounded-xl border border-outline-variant/30 shadow-sm flex flex-col gap-4 hover:border-primary/40 transition-colors"
      >
        {/* En-tête de la carte : Nom du fichier et Badges de statut */}
        <div className="flex flex-col lg:flex-row justify-between items-start gap-3 border-b border-outline-variant/20 pb-3">
          <div className="flex items-start gap-3 w-full lg:w-auto">
            <span className="material-symbols-outlined text-primary text-2xl mt-0.5">
              description
            </span>
            <div className="flex-1">
              <h4 className="font-bold text-base text-on-surface break-words leading-snug">
                {doc.file_name}
              </h4>
              <p className="text-[10px] font-mono text-on-surface-variant/60 mt-0.5">
                UUID Document: {doc.id}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="bg-secondary/10 text-secondary border border-secondary/20 px-2.5 py-1 rounded font-bold text-xs">
              {doc.file_type}
            </span>
            <span className={`px-2.5 py-1 rounded font-bold text-xs ${doc.is_validated ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'}`}>
              Validation: {doc.validation_status || (doc.is_validated ? 'VALIDATED' : 'PENDING')}
            </span>
            <span className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded font-semibold text-white ${doc.is_classified ? 'bg-green-600' : 'bg-gray-500'}`}>
              <span className="material-symbols-outlined text-sm">
                {doc.is_classified ? 'check_circle' : 'cancel'}
              </span>
              Classifié
            </span>
            <span className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded font-semibold text-white ${doc.rag_processed ? 'bg-primary' : 'bg-gray-500'}`}>
              <span className="material-symbols-outlined text-sm">
                {doc.rag_processed ? 'task_alt' : 'hourglass_empty'}
              </span>
              RAG
            </span>
          </div>
        </div>

        {/* Chemins du système sur toute la largeur (sans aucun tronquage) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 font-mono text-xs">
          {doc.file_path && (
            <div className="bg-surface-container-low p-2.5 rounded-lg border border-outline-variant/10">
              <span className="font-bold text-on-surface-variant block uppercase text-[10px] mb-1">
                Chemin d'origine (Path):
              </span>
              <span className="break-all text-on-surface select-all">
                {doc.file_path}
              </span>
            </div>
          )}

          {doc.classified_file_path && (
            <div className="bg-primary/5 p-2.5 rounded-lg border border-primary/20">
              <span className="font-bold text-primary block uppercase text-[10px] mb-1">
                Chemin Classifié (Classified Path):
              </span>
              <span className="break-all text-primary select-all">
                {doc.classified_file_path}
              </span>
            </div>
          )}
        </div>

        {/* Détails techniques, Métriques OCR et Pipeline IA */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 text-xs pt-1">
          {/* Bloc 1: Métriques Volumétriques & OCR */}
          <div className="bg-surface-container-low/50 p-3 rounded-lg border border-outline-variant/15 flex flex-col gap-1.5 font-mono">
            <span className="font-bold text-primary text-[11px] uppercase tracking-wide font-sans mb-0.5">
              Métriques Fichier & OCR
            </span>
            <div className="flex justify-between">
              <span className="text-on-surface-variant">Taille:</span>
              <span className="font-bold">{doc.file_size_mb ? `${doc.file_size_mb.toFixed(2)} MB` : 'N/A'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-on-surface-variant">Nombre de Pages:</span>
              <span className="font-bold">{doc.page_count ?? 'N/A'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-on-surface-variant">Nombre de Mots:</span>
              <span className="font-bold">{doc.word_count ?? 'N/A'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-on-surface-variant">Durée OCR:</span>
              <span className="font-bold">{doc.ocr_duration_sec ? `${doc.ocr_duration_sec}s` : 'N/A'}</span>
            </div>
            {doc.classified_at && (
              <div className="flex justify-between pt-1 border-t border-outline-variant/10 text-[11px]">
                <span className="text-on-surface-variant">Date Classification:</span>
                <span className="font-bold">{new Date(doc.classified_at).toLocaleString()}</span>
              </div>
            )}
          </div>

          {/* Bloc 2: Explications et Réponses IA */}
          <div className="lg:col-span-2 bg-surface-container-low/50 p-3 rounded-lg border border-outline-variant/15 flex flex-col gap-2">
            <span className="font-bold text-primary text-[11px] uppercase tracking-wide mb-0.5">
              Analyse & Explications IA
            </span>

            {doc.classification_reason && (
              <div>
                <span className="font-bold text-[10px] text-on-surface-variant block mb-0.5">
                  Raison de Classification:
                </span>
                <p className="bg-surface-container-lowest p-2 rounded border border-outline-variant/10 text-xs text-on-surface break-words leading-relaxed">
                  {doc.classification_reason}
                </p>
              </div>
            )}

            {doc.classification_description && (
              <div>
                <span className="font-bold text-[10px] text-on-surface-variant block mb-0.5">
                  Description Détillée:
                </span>
                <p className="text-xs text-on-surface-variant italic border-l-2 border-primary/50 pl-2 break-words">
                  {doc.classification_description}
                </p>
              </div>
            )}

            {doc.response_time && (
              <span className="text-[10px] font-mono text-on-surface-variant">
                Temps de réponse du modèle: <span className="font-bold">{doc.response_time}s</span>
              </span>
            )}
          </div>
        </div>

        {/* Bloc Accordéons (JSON & OCR Extrait) */}
        {(doc.administrative_zones?.length > 0 || doc.analysis_metadata || doc.extracted_text) && (
          <div className="flex flex-col gap-2 border-t border-outline-variant/20 pt-3">
            <div className="flex flex-wrap gap-4 text-xs font-bold">
              {doc.administrative_zones?.length > 0 && (
                <details className="w-full">
                  <summary className="cursor-pointer text-primary hover:underline">
                    Zones Administratives Extrait ({doc.administrative_zones.length})
                  </summary>
                  <pre className="text-[10px] bg-slate-900 text-green-400 p-3 rounded-lg overflow-x-auto mt-2 font-mono">
                    {JSON.stringify(doc.administrative_zones, null, 2)}
                  </pre>
                </details>
              )}

              {doc.analysis_metadata && (
                <details className="w-full">
                  <summary className="cursor-pointer text-secondary hover:underline">
                    Analyse Technique & Métadonnées IA (JSON)
                  </summary>
                  <pre className="text-[10px] bg-slate-900 text-green-400 p-3 rounded-lg overflow-x-auto mt-2 font-mono">
                    {JSON.stringify(doc.analysis_metadata, null, 2)}
                  </pre>
                </details>
              )}

              {doc.extracted_text && (
                <details className="w-full">
                  <summary className="cursor-pointer text-on-surface-variant hover:text-primary">
                    Texte Extrait Brut (Moteur OCR)
                  </summary>
                  <div className="max-h-48 overflow-y-auto bg-surface-container-low p-3 rounded-lg text-[11px] font-mono mt-2 whitespace-pre-wrap break-words border border-outline-variant/20">
                    {doc.extracted_text}
                  </div>
                </details>
              )}
            </div>
          </div>
        )}
      </div>
    ))}
  </div>
</div>
        </>
      )}
    </div>
  );
}