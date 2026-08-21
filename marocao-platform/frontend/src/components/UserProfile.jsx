import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

const STRUCTURE_TYPES = [
  { value: 'INDIVIDUAL_PROPER', label: 'Personne Physique (Propre compte)' },
  { value: 'AUTO_ENTREPRENEUR', label: 'Auto-Entrepreneur' },
  { value: 'COMPANY', label: 'Société (SARL, SA, SAS...)' },
  { value: 'PUBLIC_INSTITUTION', label: 'Établissement Public' },
  { value: 'COOPERATIVE', label: 'Coopérative' }
];

export default function UserProfile() {
  const { user, fetchWithAuth } = useAuth();
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const [structureType, setStructureType] = useState('COMPANY');
  const [profileData, setProfileData] = useState({
    manager_name: '',
    address: '',
    phone: '',
    fax: '',
    email_contact: '',
    ice: '',
    tax_professionnelle: '',
    rib: '',
    bank_name: '',
    capital_social: '',
    cin_number: '',
    auto_entrepreneur_card_number: '',
    company_name: '',
    rc_number: '',
    rc_locality: '',
    cnss_number: '',
    cooperative_register_number: '',
    legal_authorization_text: ''
  });

  useEffect(() => {
    if (user?.role === 'ADMIN') {
      setLoading(false);
      return;
    }

    const loadProfile = async () => {
      try {
        const response = await fetchWithAuth('/api/auth/profile');
        if (response.ok) {
          const data = await response.json();
          if (data.structure_type) setStructureType(data.structure_type);
          
          setProfileData({
            manager_name: data.manager_name || '',
            address: data.address || '',
            phone: data.phone || '',
            fax: data.fax || '',
            email_contact: data.email_contact || '',
            ice: data.ice || '',
            tax_professionnelle: data.tax_professionnelle || '',
            rib: data.rib || '',
            bank_name: data.bank_name || '',
            capital_social: data.capital_social !== null && data.capital_social !== undefined ? data.capital_social : '',
            cin_number: data.cin_number || '',
            auto_entrepreneur_card_number: data.auto_entrepreneur_card_number || '',
            company_name: data.company_name || '',
            rc_number: data.rc_number || '',
            rc_locality: data.rc_locality || '',
            cnss_number: data.cnss_number || '',
            cooperative_register_number: data.cooperative_register_number || '',
            legal_authorization_text: data.legal_authorization_text || ''
          });
        }
      } catch (err) {
        console.log("Aucun profil existant trouvé, prêt pour création.");
      } finally {
        setLoading(false);
      }
    };

    loadProfile();
  }, [user]);

  const handleChange = (e) => {
    setProfileData({ ...profileData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setErrorMsg('');
    setSuccessMsg('');

    const payload = {
      manager_name: profileData.manager_name,
      address: profileData.address,
      tax_professionnelle: profileData.tax_professionnelle,
      rib: profileData.rib,
      bank_name: profileData.bank_name
    };

    if (profileData.phone) payload.phone = profileData.phone;
    if (profileData.fax) payload.fax = profileData.fax;
    if (profileData.email_contact) payload.email_contact = profileData.email_contact;
    if (profileData.ice) payload.ice = profileData.ice;
    if (profileData.capital_social !== '') payload.capital_social = parseFloat(profileData.capital_social);

    if (['INDIVIDUAL_PROPER', 'AUTO_ENTREPRENEUR'].includes(structureType)) {
      payload.cin_number = profileData.cin_number;
      if (profileData.auto_entrepreneur_card_number) payload.auto_entrepreneur_card_number = profileData.auto_entrepreneur_card_number;
      if (profileData.rc_number) payload.rc_number = profileData.rc_number;
      if (profileData.rc_locality) payload.rc_locality = profileData.rc_locality;
    } else {
      payload.company_name = profileData.company_name;
      payload.rc_number = profileData.rc_number;
      payload.rc_locality = profileData.rc_locality;
      if (profileData.cnss_number) payload.cnss_number = profileData.cnss_number;
      if (profileData.cooperative_register_number) payload.cooperative_register_number = profileData.cooperative_register_number;
      if (profileData.legal_authorization_text) payload.legal_authorization_text = profileData.legal_authorization_text;
    }

    try {
      const response = await fetchWithAuth('/api/auth/profile', {
        method: 'POST',
        body: JSON.stringify({
          structure_type: structureType,
          profile_data: payload
        })
      });

      const resData = await response.json();

      if (!response.ok) {
        if (Array.isArray(resData.detail)) {
          const formatted = resData.detail.map(d => `${d.loc[d.loc.length - 1]}: ${d.msg}`).join(' | ');
          throw new Error(formatted);
        }
        throw new Error(resData.detail || 'Erreur lors de la mise à jour du profil');
      }

      setSuccessMsg(resData.message || 'Profil mis à jour avec succès !');
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (user?.role === 'ADMIN') {
    return (
      <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/30 text-center shadow-md">
        <span className="material-symbols-outlined text-4xl text-primary mb-2">admin_panel_settings</span>
        <h2 className="text-xl font-bold text-on-surface">Espace Administrateur</h2>
        <p className="text-sm text-on-surface-variant mt-1">
          Les administrateurs n'ont pas besoin de configurer de profil d'entreprise.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <span className="material-symbols-outlined animate-spin text-3xl text-primary">progress_activity</span>
      </div>
    );
  }

  return (
    <div className="bg-surface-container-lowest/90 backdrop-blur-md shadow-xl rounded-xl p-6 sm:p-8 border border-outline-variant/30 relative max-w-3xl mx-auto">
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary via-secondary-container to-primary rounded-t-xl" />

      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-outline-variant/20">
        <div className="w-12 h-12 rounded-lg bg-surface-container flex items-center justify-center text-primary">
          <span className="material-symbols-outlined text-2xl">badge</span>
        </div>
        <div>
          <h1 className="font-semibold text-2xl text-on-surface">Profil Juridique</h1>
          <p className="text-xs text-on-surface-variant">Gérez et mettez à jour les informations légales de votre structure</p>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 mb-4 bg-error-container text-on-error-container text-xs rounded-lg flex items-center gap-2">
          <span className="material-symbols-outlined text-base">error</span>
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-3 mb-4 bg-primary-container text-on-primary-container text-xs rounded-lg flex items-center gap-2">
          <span className="material-symbols-outlined text-base">check_circle</span>
          <span>{successMsg}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wider font-bold text-on-surface-variant">Type de Structure Juridique</label>
          <select
            value={structureType}
            onChange={(e) => setStructureType(e.target.value)}
            className="w-full bg-surface-container-low text-on-surface text-sm rounded-lg px-3 py-3 outline-none focus:border-primary border border-transparent transition-all"
          >
            {STRUCTURE_TYPES.map((st) => (
              <option key={st.value} value={st.value}>{st.label}</option>
            ))}
          </select>
        </div>

        {/* Champs Communs (CompanyProfile) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-on-surface-variant font-medium">Nom du Gérant / Responsable *</label>
            <input
              type="text"
              name="manager_name"
              required
              value={profileData.manager_name}
              onChange={handleChange}
              placeholder="Ex: Yassine Idrissi"
              className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
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
              className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
            />
          </div>

          <div>
            <label className="text-xs text-on-surface-variant font-medium">Téléphone</label>
            <input
              type="text"
              name="phone"
              value={profileData.phone}
              onChange={handleChange}
              placeholder="+212 600-000000"
              className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
            />
          </div>

          <div>
            <label className="text-xs text-on-surface-variant font-medium">Fax</label>
            <input
              type="text"
              name="fax"
              value={profileData.fax}
              onChange={handleChange}
              placeholder="+212 500-000000"
              className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
            />
          </div>

          <div>
            <label className="text-xs text-on-surface-variant font-medium">Email de contact</label>
            <input
              type="email"
              name="email_contact"
              value={profileData.email_contact}
              onChange={handleChange}
              placeholder="contact@entreprise.ma"
              className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
            />
          </div>

          <div>
            <label className="text-xs text-on-surface-variant font-medium">Capital Social (MAD)</label>
            <input
              type="number"
              step="any"
              name="capital_social"
              value={profileData.capital_social}
              onChange={handleChange}
              placeholder="100000"
              className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
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
              className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
            />
          </div>

          <div>
            <label className="text-xs text-on-surface-variant font-medium">Identifiant Commun de l'Entreprise (ICE)</label>
            <input
              type="text"
              name="ice"
              value={profileData.ice}
              onChange={handleChange}
              placeholder="000111222000033"
              className="w-full bg-surface-container-low text-sm font-mono rounded-lg p-3 outline-none border border-transparent focus:border-primary"
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
              className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
            />
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
              className="w-full bg-surface-container-low text-sm font-mono rounded-lg p-3 outline-none border border-transparent focus:border-primary"
            />
          </div>
        </div>

        {/* Section Personne Physique & Auto-Entrepreneur */}
        {['INDIVIDUAL_PROPER', 'AUTO_ENTREPRENEUR'].includes(structureType) && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t border-outline-variant/30 pt-4">
            <div>
              <label className="text-xs text-on-surface-variant font-medium">N° CIN *</label>
              <input
                type="text"
                name="cin_number"
                required
                value={profileData.cin_number}
                onChange={handleChange}
                placeholder="BK123456"
                className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
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
                  className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
                />
              </div>
            )}
          </div>
        )}

        {/* Section Personne Morale (Société, Public, Coopérative) */}
        {!['INDIVIDUAL_PROPER', 'AUTO_ENTREPRENEUR'].includes(structureType) && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t border-outline-variant/30 pt-4">
            <div className="sm:col-span-2">
              <label className="text-xs text-on-surface-variant font-medium">Raison Sociale / Nom de l'organisme *</label>
              <input
                type="text"
                name="company_name"
                required
                value={profileData.company_name}
                onChange={handleChange}
                placeholder="Ex: Sigma Tech SARL"
                className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
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
                className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
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
                className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
              />
            </div>

            <div>
              <label className="text-xs text-on-surface-variant font-medium">N° CNSS</label>
              <input
                type="text"
                name="cnss_number"
                value={profileData.cnss_number}
                onChange={handleChange}
                placeholder="1234567"
                className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
              />
            </div>

            {structureType === 'COOPERATIVE' && (
              <div>
                <label className="text-xs text-on-surface-variant font-medium">N° Registre des Coopératives</label>
                <input
                  type="text"
                  name="cooperative_register_number"
                  value={profileData.cooperative_register_number}
                  onChange={handleChange}
                  placeholder="COOP-REG-123"
                  className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
                />
              </div>
            )}

            <div className="sm:col-span-2">
              <label className="text-xs text-on-surface-variant font-medium">Texte d'autorisation légale / Pouvoirs</label>
              <input
                type="text"
                name="legal_authorization_text"
                value={profileData.legal_authorization_text}
                onChange={handleChange}
                placeholder="Ex: Gérant habilité par PV d'Assemblée..."
                className="w-full bg-surface-container-low text-sm rounded-lg p-3 outline-none border border-transparent focus:border-primary"
              />
            </div>
          </div>
        )}

        {/* <button
          type="submit"
          disabled={saving}
          className="w-full bg-primary text-on-primary font-semibold py-3 rounded-lg mt-4 shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2"
        >
          {saving ? (
            <span className="material-symbols-outlined animate-spin">progress_activity</span>
          ) : (
            <>
              <span className="material-symbols-outlined text-sm">save</span>
              <span>Enregistrer les modifications</span>
            </>
          )}
        </button> */}
      </form>
    </div>
  );
}