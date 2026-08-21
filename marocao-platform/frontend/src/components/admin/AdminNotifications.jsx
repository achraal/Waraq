import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function AdminNotifications() {
  const { fetchWithAuth } = useAuth();
  
  const [notifications, setNotifications] = useState([]);
  const [filter, setFilter] = useState('all'); // 'all' | 'unread' | 'read'
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const [expandedId, setExpandedId] = useState(null);

  // Charger les notifications selon le filtre sélectionné
  const fetchNotifications = async () => {
    setLoading(true);
    try {
      let endpoint = '/api/scraper/notifications';
      if (filter === 'unread') endpoint = '/api/scraper/notifications/unread';
      if (filter === 'read') endpoint = '/api/scraper/notifications/read';

      const response = await fetchWithAuth(endpoint);
      if (response.ok) {
        const data = await response.json();
        setNotifications(data.data || []);
      }
    } catch (error) {
      console.error('Erreur lors du chargement des notifications :', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
    setSelectedIds([]);
  }, [filter]);

  // Synchroniser/Récupérer les nouveaux emails
  const handleRefreshEmails = async () => {
    setRefreshing(true);
    try {
      const response = await fetchWithAuth('/api/scraper/refresh-emails', {
        method: 'POST'
      });
      if (response.ok) {
        const data = await response.json();
        alert(`Synchronisation réussie : ${data.added} nouveau(x) message(s) ajouté(s).`);
        fetchNotifications();
      }
    } catch (error) {
      console.error('Erreur lors du rafraîchissement des emails :', error);
      alert('Erreur lors de la synchronisation des emails.');
    } finally {
      setRefreshing(false);
    }
  };

  // Marquer la sélection comme lue
  const handleMarkSelectedAsRead = async () => {
    if (selectedIds.length === 0) return;
    try {
      const response = await fetchWithAuth('/api/scraper/notifications/mark-read', {
        method: 'POST',
        body: JSON.stringify(selectedIds)
      });
      if (response.ok) {
        setSelectedIds([]);
        fetchNotifications();
      }
    } catch (error) {
      console.error('Erreur lors du marquage comme lu :', error);
    }
  };

  // Marquer TOUT comme lu
  const handleMarkAllAsRead = async () => {
    try {
      const response = await fetchWithAuth('/api/scraper/notifications/mark-all-read', {
        method: 'POST'
      });
      if (response.ok) {
        setSelectedIds([]);
        fetchNotifications();
      }
    } catch (error) {
      console.error('Erreur lors du marquage complet comme lu :', error);
    }
  };

  // Gestion des cases à cocher
  const toggleSelect = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedIds.length === notifications.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(notifications.map((n) => n.id));
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto flex flex-col gap-6">
      {/* En-tête */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-on-surface">Notifications Emails (TGR)</h1>
          <p className="text-sm text-on-surface-variant">
            Avis d'appels d'offres et mises à jour reçus par email
          </p>
        </div>

        <button
          onClick={handleRefreshEmails}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg shadow-sm hover:opacity-90 disabled:opacity-50 transition-all text-sm font-medium"
        >
          <span className={`material-symbols-outlined text-lg ${refreshing ? 'animate-spin' : ''}`}>
            refresh
          </span>
          {refreshing ? 'Synchronisation...' : 'Synchroniser les Emails'}
        </button>
      </div>

      {/* Barre de Filtres et Actions en masse */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/30 shadow-sm">
        <div className="flex items-center gap-2 bg-surface-container-low p-1 rounded-lg">
          <button
            onClick={() => setFilter('all')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              filter === 'all'
                ? 'bg-surface text-on-surface shadow-xs'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
          >
            Toutes
          </button>
          <button
            onClick={() => setFilter('unread')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              filter === 'unread'
                ? 'bg-surface text-on-surface shadow-xs'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
          >
            Non lues
          </button>
          <button
            onClick={() => setFilter('read')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              filter === 'read'
                ? 'bg-surface text-on-surface shadow-xs'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
          >
            Lues
          </button>
        </div>

        <div className="flex items-center gap-2">
          {selectedIds.length > 0 && (
            <button
              onClick={handleMarkSelectedAsRead}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-secondary/10 text-secondary border border-secondary/20 rounded-lg hover:bg-secondary/20 transition-all"
            >
              <span className="material-symbols-outlined text-base">mark_email_read</span>
              Marquer la sélection comme lue ({selectedIds.length})
            </button>
          )}

          <button
            onClick={handleMarkAllAsRead}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-on-surface-variant border border-outline-variant/40 rounded-lg hover:bg-surface-container-low transition-all"
          >
            <span className="material-symbols-outlined text-base">done_all</span>
            Tout marquer comme lu
          </button>
        </div>
      </div>

      {/* Liste des Notifications */}
      {loading ? (
        <div className="flex justify-center items-center py-20 text-on-surface-variant gap-3">
          <span className="material-symbols-outlined animate-spin text-2xl">sync</span>
          Chargement des notifications...
        </div>
      ) : notifications.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 bg-surface-container-lowest border border-outline-variant/20 rounded-xl text-center">
          <span className="material-symbols-outlined text-4xl text-on-surface-variant/40 mb-2">
            mail_lock
          </span>
          <p className="text-sm font-medium text-on-surface">Aucune notification trouvée</p>
          <p className="text-xs text-on-surface-variant mt-1">
            Lancez une synchronisation pour récupérer les derniers messages.
          </p>
        </div>
      ) : (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 overflow-hidden shadow-sm">
          <div className="p-3 border-b border-outline-variant/20 bg-surface-container-low flex items-center justify-between text-xs font-semibold text-on-surface-variant">
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={selectedIds.length === notifications.length && notifications.length > 0}
                onChange={toggleSelectAll}
                className="rounded border-outline-variant/50 text-primary focus:ring-primary h-4 w-4"
              />
              <span>SÉLECTIONNER TOUT ({notifications.length})</span>
            </div>
          </div>

          <div className="divide-y divide-outline-variant/20">
            {notifications.map((n) => {
              const isSelected = selectedIds.includes(n.id);
              const isExpanded = expandedId === n.id;

              return (
                <div
                  key={n.id}
                  className={`transition-colors ${
                    !n.is_read ? 'bg-primary/5 font-medium' : 'bg-surface-container-lowest'
                  } hover:bg-surface-container-low/60`}
                >
                  <div className="p-4 flex items-start gap-4">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(n.id)}
                      className="mt-1 rounded border-outline-variant/50 text-primary focus:ring-primary h-4 w-4"
                    />

                    <span
                      className={`material-symbols-outlined text-lg mt-0.5 ${
                        !n.is_read ? 'text-primary fill-1' : 'text-on-surface-variant/40'
                      }`}
                    >
                      {!n.is_read ? 'mark_email_unread' : 'drafts'}
                    </span>

                    <div className="flex-1 min-w-0">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-1">
                        <span className="text-xs text-on-surface-variant truncate">
                          {n.sender}
                        </span>
                        <span className="text-[11px] text-on-surface-variant/70 whitespace-nowrap">
                          {n.received_at ? new Date(n.received_at).toLocaleString('fr-FR') : '-'}
                        </span>
                      </div>

                      <h3
                        onClick={() => setExpandedId(isExpanded ? null : n.id)}
                        className="text-sm font-semibold text-on-surface hover:text-primary cursor-pointer truncate"
                      >
                        {n.subject || 'Sans objet'}
                      </h3>

                      {isExpanded ? (
                        <div className="mt-3 p-3 bg-surface-container-low rounded-lg text-xs text-on-surface whitespace-pre-wrap font-mono border border-outline-variant/20">
                          {n.content}
                        </div>
                      ) : (
                        <p
                          onClick={() => setExpandedId(n.id)}
                          className="text-xs text-on-surface-variant/80 truncate mt-1 cursor-pointer"
                        >
                          {n.content}
                        </p>
                      )}
                    </div>

                    <button
                      onClick={() => setExpandedId(isExpanded ? null : n.id)}
                      className="text-on-surface-variant hover:text-on-surface p-1"
                    >
                      <span className="material-symbols-outlined text-lg">
                        {isExpanded ? 'expand_less' : 'expand_more'}
                      </span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}