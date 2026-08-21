import React, { useState } from 'react';
import { API_BASE_URL } from '../../services/api';
import { useAuth } from '../../context/AuthContext';


const STRUCTURE_TYPES = [
  { value: 'INDIVIDUAL_PROPER', label: 'Personne Physique (Propre compte)' },
  { value: 'AUTO_ENTREPRENEUR', label: 'Auto-Entrepreneur' },
  { value: 'COMPANY', label: 'Société (SARL, SA, SAS...)' },
  { value: 'PUBLIC_INSTITUTION', label: 'Établissement Public' },
  { value: 'COOPERATIVE', label: 'Coopérative' }
];

export default function Profile({ onBack, onSuccess }) {
  const { fetchWithAuth } = useAuth();
  const [structureType, setStructureType] = useState('COMPANY');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const [profileData, setProfileData] = useState({
    manager_name: '',
    address: '',
    phone: '',
    email_contact: '',
    tax_professionnelle: '',
    rib: '',
    bank_name: '',
    cin_number: '',
    auto_entrepreneur_card_number: '',
    company_name: '',
    rc_number: '',
    rc_locality: '',
    capital_social: 0,
    cooperative_register_number: '',
    legal_authorization_text: ''
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setProfileData({
      ...profileData,
      [name]: name === 'capital_social' ? parseFloat(value) || 0 : value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');

    const payloadProfileData = {
      manager_name: profileData.manager_name,
      address: profileData.address,
      tax_professionnelle: profileData.tax_professionnelle,
      rib: profileData.rib,
      bank_name: profileData.bank_name
    };

    if (profileData.phone) payloadProfileData.phone = profileData.phone;
    if (profileData.email_contact) payloadProfileData.email_contact = profileData.email_contact;

    if (structureType === 'INDIVIDUAL_PROPER') {
      payloadProfileData.cin_number = profileData.cin_number;
      if (profileData.rc_number) payloadProfileData.rc_number = profileData.rc_number;
      if (profileData.rc_locality) payloadProfileData.rc_locality = profileData.rc_locality;
    }

    if (structureType === 'AUTO_ENTREPRENEUR') {
      payloadProfileData.cin_number = profileData.cin_number;
      if (profileData.auto_entrepreneur_card_number) {
        payloadProfileData.auto_entrepreneur_card_number = profileData.auto_entrepreneur_card_number;
      }
    }

    if (['COMPANY', 'PUBLIC_INSTITUTION', 'COOPERATIVE'].includes(structureType)) {
      payloadProfileData.company_name = profileData.company_name;
      payloadProfileData.rc_number = profileData.rc_number;
      payloadProfileData.rc_locality = profileData.rc_locality;
      payloadProfileData.capital_social = profileData.capital_social;
    }

    if (structureType === 'PUBLIC_INSTITUTION') {
      payloadProfileData.legal_authorization_text = profileData.legal_authorization_text;
    }

    if (structureType === 'COOPERATIVE') {
      payloadProfileData.cooperative_register_number = profileData.cooperative_register_number;
    }

    try {
      const response = await fetchWithAuth(`/api/auth/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          structure_type: structureType,
          profile_data: payloadProfileData
        })
      });

      if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));

      // Traitement des erreurs de validation Pydantic / FastAPI (HTTP 422)
      if (Array.isArray(errorData.detail)) {
        const formattedMsg = errorData.detail
          .map(err => `${err.loc[err.loc.length - 1]}: ${err.msg}`)
          .join(' | ');
        throw new Error(formattedMsg);
      }

      throw new Error(errorData.detail || errorData.message || 'Erreur lors de la création du profil');
    }

      const data = await response.json();
      if (onSuccess) onSuccess(data);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-xl mx-auto bg-surface-container-lowest shadow-xl rounded-xl p-6 sm:p-8 border border-outline-variant/30 relative">
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary via-secondary-container to-primary" />

      <div className="flex flex-col items-center gap-2 text-center mb-6">
        <h1 className="font-semibold text-2xl text-on-surface">Configuration du Profil</h1>
        <p className="text-sm text-on-surface-variant">Étape 2/2 : Renseignez les informations juridiques</p>
      </div>

      {errorMsg && (
        <div className="p-3 mb-4 bg-error-container text-on-error-container text-xs rounded-lg flex items-center gap-2">
          <span className="material-symbols-outlined text-base">error</span>
          <span>{errorMsg}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {/* Type de Structure */}
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wider font-bold text-on-surface-variant">Type de Structure Juridique</label>
          <select
            value={structureType}
            onChange={(e) => setStructureType(e.target.value)}
            className="w-full bg-surface-container-low text-on-surface text-sm rounded-lg px-3 py-3 outline-none focus:border-primary border border-transparent"
          >
            {STRUCTURE_TYPES.map((st) => (
              <option key={st.value} value={st.value}>{st.label}</option>
            ))}
          </select>
        </div>

        {/* Champs Communs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-on-surface-variant font-medium">Nom du Gérant / Responsable *</label>
            <input
              type="text"
              name="manager_name"
              required
              value={profileData.manager_name}
              onChange={handleChange}
              placeholder="Ex: Yassine Idrissi"
              className="w-full bg-surface-container-low text-sm rounded-lg p-2.5 outline-none border border-transparent focus:border-primary"
            />
          </div>
          <div>
            <label className="text-xs text-on-surface-variant font-medium">Adresse / Domicile Élu *</label>
            <input
              type="text"
              name="address"
              required
              value={profileData.address}
              onChange={handleChange}
              placeholder="Ex: Casablanca, Maroc"
              className="w-full bg-surface-container-low text-sm rounded-lg p-2.5 outline-none border border-transparent focus:border-primary"
            />
          </div>
          <div>
            <label className="text-xs text-on-surface-variant font-medium">Taxe Professionnelle (Patente) *</label>
            <input
              type="text"
              name="tax_professionnelle"
              required
              value={profileData.tax_professionnelle}
              onChange={handleChange}
              placeholder="TP12345"
              className="w-full bg-surface-container-low text-sm rounded-lg p-2.5 outline-none border border-transparent focus:border-primary"
            />
          </div>
          <div>
            <label className="text-xs text-on-surface-variant font-medium">Nom de la Banque / TGR *</label>
            <input
              type="text"
              name="bank_name"
              required
              value={profileData.bank_name}
              onChange={handleChange}
              placeholder="Ex: Attijariwafa Bank"
              className="w-full bg-surface-container-low text-sm rounded-lg p-2.5 outline-none border border-transparent focus:border-primary"
            />
          </div>
        </div>

        <div>
          <label className="text-xs text-on-surface-variant font-medium">RIB Banque (24 chiffres) *</label>
          <input
            type="text"
            name="rib"
            required
            maxLength={24}
            value={profileData.rib}
            onChange={handleChange}
            placeholder="123456789012345678901234"
            className="w-full bg-surface-container-low text-sm font-mono rounded-lg p-2.5 outline-none border border-transparent focus:border-primary"
          />
        </div>

        {/* Personnes Physiques & Auto-Entrepreneurs */}
        {['INDIVIDUAL_PROPER', 'AUTO_ENTREPRENEUR'].includes(structureType) && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 border-t border-outline-variant/30 pt-3">
            <div>
              <label className="text-xs text-on-surface-variant font-medium">N° CIN *</label>
              <input
                type="text"
                name="cin_number"
                required
                value={profileData.cin_number}
                onChange={handleChange}
                placeholder="BK123456"
                className="w-full bg-surface-container-low text-sm rounded-lg p-2.5 outline-none border border-transparent focus:border-primary"
              />
            </div>
            {structureType === 'AUTO_ENTREPRENEUR' && (
              <div>
                <label className="text-xs text-on-surface-variant font-medium">N° Carte Auto-Entrepreneur</label>
                <input
                  type="text"
                  name="auto_entrepreneur_card_number"
                  value={profileData.auto_entrepreneur_card_number}
                  onChange={handleChange}
                  placeholder="AE999888"
                  className="w-full bg-surface-container-low text-sm rounded-lg p-2.5 outline-none border border-transparent focus:border-primary"
                />
              </div>
            )}
          </div>
        )}

        {/* Personnes Morales (Société, Public, Coopérative) */}
        {['COMPANY', 'PUBLIC_INSTITUTION', 'COOPERATIVE'].includes(structureType) && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 border-t border-outline-variant/30 pt-3">
            <div className="sm:col-span-2">
              <label className="text-xs text-on-surface-variant font-medium">Raison Sociale / Nom *</label>
              <input
                type="text"
                name="company_name"
                required
                value={profileData.company_name}
                onChange={handleChange}
                placeholder="Ex: Sigma Tech SARL"
                className="w-full bg-surface-container-low text-sm rounded-lg p-2.5 outline-none border border-transparent focus:border-primary"
              />
            </div>
            <div>
              <label className="text-xs text-on-surface-variant font-medium">N° Registre du Commerce (RC) *</label>
              <input
                type="text"
                name="rc_number"
                required
                value={profileData.rc_number}
                onChange={handleChange}
                placeholder="RC444555"
                className="w-full bg-surface-container-low text-sm rounded-lg p-2.5 outline-none border border-transparent focus:border-primary"
              />
            </div>
            <div>
              <label className="text-xs text-on-surface-variant font-medium">Localité RC *</label>
              <input
                type="text"
                name="rc_locality"
                required
                value={profileData.rc_locality}
                onChange={handleChange}
                placeholder="Ex: Casablanca"
                className="w-full bg-surface-container-low text-sm rounded-lg p-2.5 outline-none border border-transparent focus:border-primary"
              />
            </div>
            <div>
              <label className="text-xs text-on-surface-variant font-medium">Capital Social (MAD)</label>
              <input
                type="number"
                name="capital_social"
                value={profileData.capital_social}
                onChange={handleChange}
                placeholder="500000"
                className="w-full bg-surface-container-low text-sm rounded-lg p-2.5 outline-none border border-transparent focus:border-primary"
              />
            </div>
          </div>
        )}

        {/* Spécifique Établissement Public */}
        {structureType === 'PUBLIC_INSTITUTION' && (
          <div className="border-t border-outline-variant/30 pt-3">
            <label className="text-xs text-on-surface-variant font-medium">Texte d'habilitation légale</label>
            <textarea
              name="legal_authorization_text"
              value={profileData.legal_authorization_text}
              onChange={handleChange}
              placeholder="Ex: Décret n°2-XX-XXX..."
              className="w-full bg-surface-container-low text-sm rounded-lg p-2.5 outline-none border border-transparent focus:border-primary h-20"
            />
          </div>
        )}

        {/* Spécifique Coopérative */}
        {structureType === 'COOPERATIVE' && (
          <div className="border-t border-outline-variant/30 pt-3">
            <label className="text-xs text-on-surface-variant font-medium">N° Registre des Coopératives</label>
            <input
              type="text"
              name="cooperative_register_number"
              value={profileData.cooperative_register_number}
              onChange={handleChange}
              placeholder="COOP-REG-123"
              className="w-full bg-surface-container-low text-sm rounded-lg p-2.5 outline-none border border-transparent focus:border-primary"
            />
          </div>
        )}

        <div className="flex gap-2 mt-4">
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="w-1/3 bg-surface-container text-on-surface text-sm font-semibold py-3 rounded-lg"
            >
              Retour
            </button>
          )}
          <button
            type="submit"
            disabled={loading}
            className="flex-1 bg-primary text-on-primary text-sm font-semibold py-3 rounded-lg flex items-center justify-center gap-2"
          >
            {loading ? (
              <span className="material-symbols-outlined animate-spin">progress_activity</span>
            ) : (
              <span>Enregistrer le Profil</span>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}