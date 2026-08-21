import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Sidebar from '../components/Sidebar';

export default function MainLayout() {
  const { token } = useAuth();

  // Redirection automatique si l'utilisateur n'est pas connecté
  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div 
      className="relative flex min-h-screen w-full bg-cover bg-center bg-no-repeat overflow-hidden"
      style={{ backgroundImage: "url('/background.png')" }}
    >
      {/* 1. Voile d'arrière-plan avec flou pour maintenir une excellente lisibilité */}
      <div className="absolute inset-0 bg-surface/85 backdrop-blur-sm z-0" />

      {/* 2. Barre latérale (Sidebar) */}
      <div className="relative z-10 flex shrink-0">
        <Sidebar />
      </div>

      {/* 3. Conteneur de contenu principal */}
      <main className="relative z-10 flex-1 h-screen overflow-y-auto p-4 sm:p-6 md:p-8">
        <div className="max-w-7xl mx-auto w-full">
          <Outlet />
        </div>
      </main>
    </div>
  );
}