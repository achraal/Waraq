import React, { useState } from 'react';
import { API_BASE_URL } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

export default function Login({ onSwitchToRegister, onSuccess }) {
  const { saveToken } = useAuth();
  const [credentials, setCredentials] = useState({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleChange = (e) => {
    setCredentials({ ...credentials, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials)
      });

      if (!response.ok) throw new Error('Identifiants invalides ou erreur serveur');

      const data = await response.json();
      if (data.access_token) {
        saveToken(data.access_token); // Stocke le token dans le Context & localStorage
      }
      if (onSuccess) onSuccess(data);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    /* Conteneur global occupant tout l'écran avec l'image en arrière-plan */
    <div 
      className="min-h-screen w-full flex items-center justify-center md:justify-end p-4 md:pr-16 lg:pr-24 bg-cover bg-center bg-no-repeat"
      style={{ backgroundImage: "url('/background.png')" }} // 👈 Indiquez le chemin de votre image ici
    >
      {/* Carte du formulaire conservée à l'identique (aucune transparence, taille d'origine) */}
      <div className="w-full max-w-md bg-surface-container-lowest shadow-xl rounded-xl p-6 sm:p-8 border border-outline-variant/30 relative">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary via-secondary-container to-primary rounded-t-xl" />
        
        <div className="flex flex-col items-center gap-2 text-center mb-6">
          <div className="w-16 h-16 rounded-lg bg-surface-container flex items-center justify-center shadow-sm">
            <img src="/logo.png" alt="Waraq Logo" className="w-full h-full object-contain p-2" />
          </div>
          <h1 className="font-semibold text-2xl text-on-surface">Bon retour parmi nous</h1>
          <p className="text-sm text-on-surface-variant">Accédez à votre espace de gestion documentaire</p>
        </div>

        {errorMsg && (
          <div className="p-3 mb-4 bg-error-container text-on-error-container text-xs rounded-lg flex items-center gap-2">
            <span className="material-symbols-outlined text-base">error</span>
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs uppercase tracking-wider font-bold text-on-surface-variant">Adresse Email</label>
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-3 text-on-surface-variant/50 text-[20px]">mail</span>
              <input
                name="email"
                type="email"
                required
                value={credentials.email}
                onChange={handleChange}
                placeholder="nom@entreprise.ma"
                className="w-full bg-surface-container-low text-on-surface text-sm rounded-lg pl-10 pr-4 py-3 outline-none focus:bg-surface-container-lowest border border-transparent focus:border-primary transition-all"
              />
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex justify-between items-center">
              <label className="text-xs uppercase tracking-wider font-bold text-on-surface-variant">Mot de passe</label>
              <a href="#" className="text-xs text-primary hover:underline">Mot de passe oublié ?</a>
            </div>
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-3 text-on-surface-variant/50 text-[20px]">lock</span>
              <input
                name="password"
                type={showPassword ? 'text' : 'password'}
                required
                value={credentials.password}
                onChange={handleChange}
                placeholder="••••••••"
                className="w-full bg-surface-container-low text-on-surface font-mono text-sm rounded-lg pl-10 pr-10 py-3 outline-none focus:bg-surface-container-lowest border border-transparent focus:border-primary transition-all"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 text-on-surface-variant/50 hover:text-on-surface"
              >
                <span className="material-symbols-outlined text-[20px]">
                  {showPassword ? 'visibility_off' : 'visibility'}
                </span>
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary text-on-primary font-semibold py-3 rounded-lg mt-2 shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2"
          >
            {loading ? (
              <span className="material-symbols-outlined animate-spin">progress_activity</span>
            ) : (
              <>
                <span>Se connecter</span>
                <span className="material-symbols-outlined text-sm">arrow_forward</span>
              </>
            )}
          </button>
        </form>

        <div className="flex items-center justify-center gap-2 text-sm mt-6 pt-4 border-t border-outline-variant/20">
          <span className="text-on-surface-variant">Nouveau sur Waraq ?</span>
          <button type="button" onClick={onSwitchToRegister} className="text-primary font-semibold hover:underline">
            Créer un compte
          </button>
        </div>
      </div>
    </div>
  );
}