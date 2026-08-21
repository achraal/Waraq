import React, { createContext, useContext, useState, useEffect } from 'react';
import { API_BASE_URL } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('access_token') || null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // 1. Sauvegarder/Supprimer le token
  const saveToken = (newToken) => {
    setToken(newToken);
    if (newToken) {
      localStorage.setItem('access_token', newToken);
    } else {
      localStorage.removeItem('access_token');
    }
  };

  // 2. Déclaration de logout
  const logout = () => {
    saveToken(null);
    setUser(null);
  };

  // 3. Helper pour requêtes authentifiées
  const fetchWithAuth = async (url, options = {}) => {
    const currentToken = localStorage.getItem('access_token') || token;

    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {})
    };

    const response = await fetch(`${API_BASE_URL}${url}`, { ...options, headers });
    
    if (response.status === 401) {
      logout();
      throw new Error('Session expirée, veuillez vous reconnecter');
    }

    return response;
  };

  // 4. Charger les données de l'utilisateur au démarrage via /api/auth/me
  useEffect(() => {
    const initAuth = async () => {
      const currentToken = localStorage.getItem('access_token');
      if (currentToken) {
        try {
          const response = await fetchWithAuth('/api/auth/me');
          if (response.ok) {
            const userData = await response.json();
            setUser(userData); // Contient { id, email, role }
          } else {
            logout();
          }
        } catch (err) {
          console.error("Erreur lors de la récupération du profil :", err);
          logout();
        }
      } else {
        setUser(null);
      }
      setLoading(false);
    };

    initAuth();
  }, [token]);

  return (
    <AuthContext.Provider value={{ token, user, setUser, saveToken, logout, fetchWithAuth, loading }}>
      {!loading && children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);