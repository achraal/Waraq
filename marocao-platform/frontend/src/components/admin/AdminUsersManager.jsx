import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function AdminUsersManager() {
  const { fetchWithAuth } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [userToDelete, setUserToDelete] = useState(null);
  
  // États de gestion des modales
  const [selectedUser, setSelectedUser] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [editProfileData, setEditProfileData] = useState(null);
  const [structureType, setStructureType] = useState('SARL');

  const PHYSICAL_TYPES = ['INDIVIDUAL_PROPER', 'AUTO_ENTREPRENEUR'];

  const loadUsers = async () => {
    setLoading(true);
    try {
      const response = await fetchWithAuth('/api/auth/admin/users');
      if (response.ok) {
        const data = await response.json();
        setUsers(data);
      } else {
        setError('Erreur lors de la récupération des utilisateurs');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const confirmDeleteUser = async () => {
    if (!userToDelete) return;
    try {
      const response = await fetchWithAuth(`/admin/users/${userToDelete.id}`, { method: 'DELETE' });
      if (response.ok) {
        setUsers(users.filter(u => u.id !== userToDelete.id));
        setUserToDelete(null);
      } else {
        const errData = await response.json();
        alert(`Échec de la suppression : ${errData.detail}`);
      }
    } catch (err) {
      alert("Erreur lors de la suppression : " + err.message);
    }
  };

  const handleUpdatePassword = async (userId) => {
    if (!newPassword) return alert("Veuillez saisir un mot de passe");
    try {
      const response = await fetchWithAuth(`/api/auth/admin/users/${userId}/password`, {
        method: 'PATCH',
        body: JSON.stringify({ new_password: newPassword })
      });
      if (response.ok) {
        alert("Mot de passe mis à jour avec succès");
        setNewPassword('');
        setSelectedUser(null);
      } else {
        alert("Erreur lors de la modification du mot de passe");
      }
    } catch (err) {
      alert("Erreur serveur : " + err.message);
    }
  };

  const handleSaveProfile = async (userId) => {
    try {
      const response = await fetchWithAuth(`/api/auth/admin/users/${userId}/profile`, {
        method: 'PUT',
        body: JSON.stringify({
          structure_type: structureType,
          profile_data: editProfileData
        })
      });
      if (response.ok) {
        alert("Profil utilisateur mis à jour !");
        setEditProfileData(null);
        setSelectedUser(null);
        loadUsers();
      } else {
        const errData = await response.json();
        alert(`Erreur : ${errData.detail}`);
      }
    } catch (err) {
      alert("Erreur serveur : " + err.message);
    }
  };

  const handleChange = (field, value) => {
    setEditProfileData(prev => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-on-surface-variant font-sans">
        <span className="material-symbols-outlined animate-spin text-3xl text-primary mr-3">progress_activity</span>
        <span className="font-medium">Chargement des utilisateurs...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-error-container text-on-error-container rounded-lg border border-outline-variant flex items-center gap-3">
        <span className="material-symbols-outlined text-error">error</span>
        <span className="font-medium">{error}</span>
      </div>
    );
  }

  const isPhysical = PHYSICAL_TYPES.includes(structureType);

  return (
    <div className="p-6 max-w-7xl mx-auto bg-transparent text-on-background font-sans">
      
      {/* En-tête */}
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-outline-variant">
        <div>
          <h1 className="text-3xl font-bold text-primary tracking-tight">Gestion des Utilisateurs</h1>
          <p className="text-sm text-on-surface-variant mt-1">Administration de la plateforme et des accès aux profils</p>
        </div>
        <div className="px-4 py-2 bg-surface-container-high rounded-full border border-outline-variant text-xs font-mono text-on-surface-variant">
          Total : <strong className="text-primary">{users.length}</strong>
        </div>
      </div>

      {/* Tableau des utilisateurs */}
      <div className="bg-surface-container-lowest shadow-md rounded-xl border border-outline-variant overflow-hidden">
        <table className="min-w-full divide-y divide-outline-variant">
          <thead className="bg-surface-container-low">
            <tr>
              <th className="px-6 py-4 text-left text-xs font-bold text-on-surface-variant uppercase tracking-wider">Email</th>
              <th className="px-6 py-4 text-left text-xs font-bold text-on-surface-variant uppercase tracking-wider">Rôle</th>
              <th className="px-6 py-4 text-left text-xs font-bold text-on-surface-variant uppercase tracking-wider">Type de Structure</th>
              <th className="px-6 py-4 text-right text-xs font-bold text-on-surface-variant uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant bg-surface-container-lowest">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-surface-container-low/60 transition-colors">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-on-surface">
                  {u.email}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold font-mono ${
                    u.role === 'ADMIN' 
                      ? 'bg-primary-container text-on-primary-container' 
                      : 'bg-surface-container-highest text-on-surface-variant'
                  }`}>
                    {u.role}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-on-surface-variant">
                  {u.company_profile ? (
                    <span className="inline-flex items-center gap-1 font-mono text-xs bg-tertiary-container/20 text-tertiary px-2 py-1 rounded">
                      <span className="material-symbols-outlined text-sm">corporate_fare</span>
                      {u.company_profile.structure_type}
                    </span>
                  ) : (
                    <span className="text-outline italic text-xs">Aucun profil</span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-1">
                  {u.role !== 'ADMIN' && (
                    <button
                      onClick={() => {
                        setSelectedUser(u);
                        setEditProfileData(u.company_profile || {});
                        setStructureType(u.company_profile?.structure_type || 'SARL');
                      }}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-primary hover:bg-primary-fixed/40 transition-colors"
                    >
                      <span className="material-symbols-outlined text-base">edit</span>
                      Profil
                    </button>
                  )}
                  <button
                    onClick={() => { setSelectedUser(u); setEditProfileData(null); }}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-tertiary hover:bg-tertiary-fixed/40 transition-colors"
                  >
                    <span className="material-symbols-outlined text-base">key</span>
                    Mot de passe
                  </button>
                  {u.role !== 'ADMIN' && (
                    <button
                      onClick={() => setUserToDelete(u)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-error hover:bg-error-container/50 transition-colors"
                    >
                      <span className="material-symbols-outlined text-base">delete</span>
                      Supprimer
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal Édition de profil */}
      {selectedUser && editProfileData && (
        <div className="fixed inset-0 bg-inverse-surface/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-surface-container-lowest rounded-xl p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto border border-outline-variant shadow-2xl">
            <div className="flex justify-between items-center mb-6 pb-3 border-b border-outline-variant">
              <div>
                <h2 className="text-xl font-bold text-primary">Édition du profil</h2>
                <p className="text-xs font-mono text-on-surface-variant">{selectedUser.email}</p>
              </div>
              <button 
                onClick={() => { setSelectedUser(null); setEditProfileData(null); }}
                className="p-1 rounded-full text-on-surface-variant hover:bg-surface-container-high transition-colors"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            
            <div className="mb-6 bg-surface-container-low p-4 rounded-xl border border-outline-variant">
              <label className="block text-xs font-bold uppercase text-on-surface-variant mb-2">Structure Juridique</label>
              <select
                value={structureType}
                onChange={(e) => setStructureType(e.target.value)}
                className="w-full border border-outline rounded-lg p-2.5 bg-surface-container-lowest text-on-surface focus:outline-none focus:ring-2 focus:ring-primary text-sm font-medium"
              >
                <option value="SARL">Société à Responsabilité Limitée (SARL)</option>
                <option value="SA">Société Anonyme (SA)</option>
                <option value="SNC">Société en Nom Collectif (SNC)</option>
                <option value="AUTO_ENTREPRENEUR">Auto-Entrepreneur</option>
                <option value="INDIVIDUAL_PROPER">Personne Physique / En propre</option>
                <option value="COOPERATIVE">Coopérative</option>
                <option value="PUBLIC_ESTABLISHMENT">Établissement Public</option>
              </select>
            </div>

            {/* Section 1 : Champs Communs */}
            <div className="mb-6">
              <h3 className="text-sm font-bold text-primary uppercase tracking-wide border-b border-outline-variant pb-2 mb-4">
                1. Informations Générales & Communes
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant mb-1">Responsable *</label>
                  <input type="text" value={editProfileData.manager_name || ''} onChange={(e) => handleChange('manager_name', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant mb-1">Adresse *</label>
                  <input type="text" value={editProfileData.address || ''} onChange={(e) => handleChange('address', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant mb-1">Téléphone</label>
                  <input type="text" value={editProfileData.phone || ''} onChange={(e) => handleChange('phone', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant mb-1">Fax</label>
                  <input type="text" value={editProfileData.fax || ''} onChange={(e) => handleChange('fax', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant mb-1">Email Contact</label>
                  <input type="email" value={editProfileData.email_contact || ''} onChange={(e) => handleChange('email_contact', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant mb-1">ICE</label>
                  <input type="text" value={editProfileData.ice || ''} onChange={(e) => handleChange('ice', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary font-mono text-xs" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant mb-1">Taxe Professionnelle *</label>
                  <input type="text" value={editProfileData.tax_professionnelle || ''} onChange={(e) => handleChange('tax_professionnelle', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant mb-1">RIB (24 chiffres) *</label>
                  <input type="text" value={editProfileData.rib || ''} onChange={(e) => handleChange('rib', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary font-mono text-xs" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant mb-1">Banque / Organisme *</label>
                  <input type="text" value={editProfileData.bank_name || ''} onChange={(e) => handleChange('bank_name', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant mb-1">Capital Social (DH)</label>
                  <input type="number" step="any" value={editProfileData.capital_social || ''} onChange={(e) => handleChange('capital_social', parseFloat(e.target.value) || null)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                </div>
              </div>
            </div>

            {/* Section 2 : Spécifique Personne Physique ou Morale */}
            {isPhysical ? (
              <div className="mb-6">
                <h3 className="text-sm font-bold text-primary uppercase tracking-wide border-b border-outline-variant pb-2 mb-4">
                  2. Spécifique Personne Physique / Auto-Entrepreneur
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1">CIN *</label>
                    <input type="text" value={editProfileData.cin_number || ''} onChange={(e) => handleChange('cin_number', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary font-mono text-xs" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1">N° Carte Auto-Entrepreneur</label>
                    <input type="text" value={editProfileData.auto_entrepreneur_card_number || ''} onChange={(e) => handleChange('auto_entrepreneur_card_number', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1">Numéro RC</label>
                    <input type="text" value={editProfileData.rc_number || ''} onChange={(e) => handleChange('rc_number', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1">Localité RC</label>
                    <input type="text" value={editProfileData.rc_locality || ''} onChange={(e) => handleChange('rc_locality', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                  </div>
                </div>
              </div>
            ) : (
              <div className="mb-6">
                <h3 className="text-sm font-bold text-primary uppercase tracking-wide border-b border-outline-variant pb-2 mb-4">
                  2. Spécifique Personne Morale / Société / Coopérative
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1">Raison Sociale *</label>
                    <input type="text" value={editProfileData.company_name || ''} onChange={(e) => handleChange('company_name', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1">Numéro RC *</label>
                    <input type="text" value={editProfileData.rc_number || ''} onChange={(e) => handleChange('rc_number', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary font-mono text-xs" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1">Localité RC *</label>
                    <input type="text" value={editProfileData.rc_locality || ''} onChange={(e) => handleChange('rc_locality', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1">CNSS</label>
                    <input type="text" value={editProfileData.cnss_number || ''} onChange={(e) => handleChange('cnss_number', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1">N° Registre Coopératives</label>
                    <input type="text" value={editProfileData.cooperative_register_number || ''} onChange={(e) => handleChange('cooperative_register_number', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1">Autorisation Légale / Agrément</label>
                    <textarea rows="2" value={editProfileData.legal_authorization_text || ''} onChange={(e) => handleChange('legal_authorization_text', e.target.value)} className="w-full border border-outline rounded-lg p-2 bg-surface text-on-surface focus:ring-2 focus:ring-primary" placeholder="Ex: Décret ou Arrêté portant création..." />
                  </div>
                </div>
              </div>
            )}

            <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-outline-variant">
              <button
                onClick={() => { setSelectedUser(null); setEditProfileData(null); }}
                className="px-4 py-2 border border-outline text-on-surface-variant rounded-lg font-medium hover:bg-surface-container-high transition-colors text-sm"
              >
                Annuler
              </button>
              <button
                onClick={() => handleSaveProfile(selectedUser.id)}
                className="px-5 py-2 bg-primary text-on-primary rounded-lg font-semibold hover:bg-primary-container transition-colors shadow-sm text-sm"
              >
                Enregistrer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Réinitialisation Mot de passe */}
      {selectedUser && !editProfileData && (
        <div className="fixed inset-0 bg-inverse-surface/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-surface-container-lowest rounded-xl p-6 max-w-md w-full border border-outline-variant shadow-2xl">
            <div className="flex items-center gap-3 text-tertiary mb-3">
              <span className="material-symbols-outlined text-2xl">lock_reset</span>
              <h2 className="text-lg font-bold">Réinitialiser le mot de passe</h2>
            </div>
            <p className="text-xs font-mono text-on-surface-variant mb-4 bg-surface-container-low p-2 rounded">
              Compte : {selectedUser.email}
            </p>
            <input
              type="password"
              placeholder="Nouveau mot de passe"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full border border-outline rounded-lg p-2.5 mb-6 text-sm bg-surface text-on-surface focus:ring-2 focus:ring-tertiary focus:outline-none"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setSelectedUser(null); setNewPassword(''); }}
                className="px-4 py-2 border border-outline text-on-surface-variant rounded-lg font-medium hover:bg-surface-container-high text-sm transition-colors"
              >
                Annuler
              </button>
              <button
                onClick={() => handleUpdatePassword(selectedUser.id)}
                className="px-4 py-2 bg-tertiary text-on-tertiary rounded-lg font-semibold hover:bg-tertiary-container transition-colors text-sm"
              >
                Valider
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Confirmation de Suppression */}
      {userToDelete && (
        <div className="fixed inset-0 bg-inverse-surface/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-surface-container-lowest rounded-xl p-6 max-w-md w-full shadow-2xl border border-outline-variant">
            <div className="flex items-center gap-3 text-error mb-3">
              <span className="material-symbols-outlined text-3xl">warning</span>
              <h3 className="text-lg font-bold">Confirmer la suppression</h3>
            </div>
            
            <p className="text-sm text-on-surface-variant mb-6 leading-relaxed">
              Êtes-vous sûr de vouloir supprimer définitivement l'utilisateur{' '}
              <strong className="text-on-surface font-semibold">{userToDelete.email}</strong> ainsi que son profil entreprise ? 
              Cette action est irréversible.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setUserToDelete(null)}
                className="px-4 py-2 text-sm font-medium border border-outline text-on-surface-variant rounded-lg hover:bg-surface-container-high transition-colors"
              >
                Annuler
              </button>
              <button
                onClick={confirmDeleteUser}
                className="px-4 py-2 text-sm font-semibold bg-error text-on-error rounded-lg hover:bg-error-container transition-colors shadow-sm"
              >
                Supprimer définitivement
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}