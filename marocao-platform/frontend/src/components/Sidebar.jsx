import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Sidebar() {
  const { user, logout, fetchWithAuth } = useAuth();
  const navigate = useNavigate();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  // Définition du rôle (par défaut CANDIDATE si non spécifié)
  const userRole = user?.role?.toUpperCase() || 'CANDIDATE';

  // Récupération dynamique du compteur de notifications non lues
  useEffect(() => {
    if (userRole === 'ADMIN') {
      const fetchUnreadCount = async () => {
        try {
          const res = await fetchWithAuth('/api/scraper/notifications/unread');
          if (res.ok) {
            const data = await res.json();
            setUnreadCount(data.total || 0);
          }
        } catch (error) {
          console.error('Erreur chargement compteur notifications:', error);
        }
      };

      fetchUnreadCount();
    }
  }, [userRole]);

  // Configuration des menus selon le rôle
  const adminLinks = [
    { path: '/dashboard', label: 'Dashboard & Télémétrie', icon: 'dashboard' },
    { path: '/userprofile', label: 'Profil', icon: 'person' },
    { path: '/admin/users', label: 'Utilisateurs', icon: 'group' }, 
    {
      path: '/admin/notifications',
      label: 'Notifications',
      icon: 'notifications',
      badge: unreadCount > 0 ? unreadCount : null,
    },
    { path: '/admin/vectors', label: 'Espace Vectoriel (RAG)', icon: 'hub' },
    { path: '/tenders', label: 'Appels d\'offres', icon: 'list_alt' },
    { path: '/tenders-full', label: 'Base Tenders', icon: 'table_view' },
    { path: '/scraper', label: 'Gestion Scraper', icon: 'web' },
    { path: '/classifier', label: 'Moteur IA (IDP)', icon: 'smart_toy' },
    { path: '/admin/intelligence', label: 'Moteur IA (FT)', icon: 'memory' },
    { path: '/runner', label: 'Exécution IA Globale', icon: 'play_circle' },
  ];

  const candidateLinks = [
    { path: '/userprofile', label: 'Profil', icon: 'person' },
    { path: '/tenders', label: 'Appels d\'offres', icon: 'list_alt' },
    { path: '/scraper', label: 'Gestion Scraper', icon: 'web' },
    { path: '/classifier', label: 'Moteur IA (IDP)', icon: 'smart_toy' },
    { path: '/runner', label: 'Exécution IA Globale', icon: 'play_circle' },
    
  ];

  const navItems = userRole === 'ADMIN' ? adminLinks : candidateLinks;

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside
      // On enlève "justify-between" ici car c're le flex-1 du milieu qui va pousser les éléments
      className={`h-screen bg-surface-container-lowest border-r border-outline-variant/30 flex flex-col transition-all duration-300 relative ${
        isCollapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Bouton Toggle (Rétracter / Agrandir) */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="absolute -right-3 top-7 bg-surface-container-high text-on-surface border border-outline-variant/40 rounded-full p-1 shadow-md hover:bg-surface-container transition-all z-20 flex items-center justify-center"
        title={isCollapsed ? 'Déplier la barre' : 'Replier la barre'}
      >
        <span className="material-symbols-outlined text-sm">
          {isCollapsed ? 'chevron_right' : 'chevron_left'}
        </span>
      </button>

      {/* --- 1. EN-TÊTE FIXE (shrink-0 empêche l'écrasement) --- */}
      <div className="flex items-center gap-3 p-4 border-b border-outline-variant/20 overflow-hidden h-20 shrink-0">
        <div className="w-10 h-10 min-w-[40px] rounded-lg bg-surface-container flex items-center justify-center shadow-sm">
          <img src="/logo.png" alt="Waraq Logo" className="w-full h-full object-contain p-1.5" />
        </div>
        {!isCollapsed && (
          <div className="flex flex-col whitespace-nowrap">
            <span className="font-semibold text-lg text-on-surface">Waraq</span>
            <span className="text-[10px] uppercase font-bold tracking-wider text-primary">
              Espace {userRole === 'ADMIN' ? 'Administrateur' : 'Candidat'}
            </span>
          </div>
        )}
      </div>

      {/* --- 2. ZONE SCROLLABLE (flex-1 prend tout l'espace libre, overflow-y-auto active le scroll) --- */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden">
        <nav className="p-3 flex flex-col gap-1.5 mt-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center justify-between px-3 py-3 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-primary text-on-primary shadow-sm'
                    : 'text-on-surface-variant hover:bg-primary/10 hover:text-primary'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="material-symbols-outlined text-[22px] min-w-[24px]">
                      {item.icon}
                    </span>
                    {!isCollapsed && (
                      <span className="truncate whitespace-nowrap">{item.label}</span>
                    )}
                  </div>

                  {/* Affichage du Badge si présent */}
                  {item.badge && (
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full min-w-[20px] text-center shadow-sm transition-colors ${
                        isActive
                          ? 'bg-on-primary text-primary'
                          : 'bg-primary/15 text-primary'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* --- 3. PIED DE PAGE FIXE (shrink-0) --- */}
      <div className="p-3 border-t border-outline-variant/20 flex flex-col gap-2 shrink-0">
        {!isCollapsed && user && (
          <div className="px-2 py-1.5 flex flex-col truncate">
            <span className="text-xs font-semibold text-on-surface truncate">
              {user.email || 'Utilisateur'}
            </span>
            <span className="text-[10px] text-on-surface-variant uppercase tracking-wider font-bold">
              {userRole}
            </span>
          </div>
        )}

        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-error hover:bg-error-container/20 transition-all w-full text-left"
          title="Se déconnecter"
        >
          <span className="material-symbols-outlined text-[22px] min-w-[24px]">
            logout
          </span>
          {!isCollapsed && <span className="whitespace-nowrap">Déconnexion</span>}
        </button>
      </div>
    </aside>
  );
}