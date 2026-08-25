import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'
import { Routes, Route, useNavigate } from 'react-router-dom'
import LandingPage from './components/LandingPage'
import Login from './components/auth/Login'
import Register from './components/auth/Register'
import Profile from './components/auth/Profile'
import UserProfile from './components/UserProfile';
import MainLayout from './layouts/MainLayout';
import AdminUsersManager from './components/admin/AdminUsersManager';
import Dashboard from './components/dashboard/Dashboard';
import AdminNotifications from './components/admin/AdminNotifications';
import AdminVectorVisualizer from './components/admin/AdminVectorVisualizer';
import TendersMinimal from './components/tenders/TendersMinimal';
import TenderDetail from './components/tenders/TenderDetail';
import TendersFullList from './components/tenders/TendersFullList';
import ScraperManager from './components/ScraperManager';
import DocumentClassifier from './components/classifier/DocumentClassifier';
import TenderDocumentClassifier from './components/classifier/TenderDocumentClassifier';
import AdminIntelligenceEngine from './components/admin/AdminIntelligenceEngine';
import DocumentValidator from './components/classifier/DocumentValidator';
import GlobalClassificationRunner from './components/classifier/GlobalClassificationRunner';
import RagViewer from './components/rag/RagViewer';
import TenderRagRunner from './components/rag/TenderRagRunner';
import DocumentRagRunner from './components/rag/DocumentRagRunner';
import GlobalRagManager from './components/rag/GlobalRagManager';
import WorkflowManager from './components/workflow/WorkflowManager';

function App() {
  const navigate = useNavigate();

  return(
  <Routes>
      {/* Route principale */}
      <Route path="/" element={<LandingPage />} />

      {/* Route de connexion */}
      <Route 
        path="/login" 
        element={
          <Login 
            onSwitchToRegister={() => navigate('/register')} 
            onSuccess={(data) => {
              console.log('Connexion réussie:', data);
              navigate('/dashboard'); // Rediriger vers votre tableau de bord
            }} 
          />
        } 
      />

      {/* Route de création de compte (Étape 1) */}
      <Route 
        path="/register" 
        element={
          <Register 
            onSwitchToLogin={() => navigate('/login')} 
            onSuccessStep1={(data) => {
              console.log('Étape 1 réussie:', data);
              navigate('/profile'); // Passer à la configuration du profil
            }} 
          />
        } 
      />

      {/* Route de configuration du profil (Étape 2) */}
      <Route 
        path="/profile" 
        element={
          <Profile 
            onBack={() => navigate('/register')} 
            onSuccess={(data) => {
              console.log('Profil enregistré avec succès:', data);
              navigate('/login');
            }} 
          />
        } 
      />
      {/* Routes Protégées (avec Sidebar) */}
      <Route element={<MainLayout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/userprofile" element={<UserProfile />} />
        <Route path="/admin/users" element={<AdminUsersManager />} />
        <Route path="/admin/notifications" element={<AdminNotifications />} />
        <Route path="/admin/vectors" element={<AdminVectorVisualizer />} />
        {/* Vue minimale (Candidats et Admins) */}
        <Route path="/tenders" element={<TendersMinimal />} />
        {/* Vue détaillée (Candidats et Admins) */}
        <Route path="/tenders/:id" element={<TenderDetail />} />
        {/* Vue tableau complet (Plutôt pour Admins, optionnel dans le menu) */}
        <Route path="/tenders-full" element={<TendersFullList />} />
        <Route path="/scraper" element={<ScraperManager />} />
        <Route path="/classifier" element={<DocumentClassifier />} />
        <Route path="/tenders/:id/classifier" element={<TenderDocumentClassifier />} />
        <Route path="/admin/intelligence" element={<AdminIntelligenceEngine />} />
        <Route path="/tenders/:tenderId/document/:documentId/validate" element={<DocumentValidator />} />
        <Route path="/runner" element={<GlobalClassificationRunner />} />
        <Route path="/rag/viewer" element={<RagViewer />} />
        <Route path="/rag/manager" element={<GlobalRagManager />} />
        <Route path="/rag/tender/:tenderId" element={<TenderRagRunner />} />
        <Route path="/rag/document/:docId" element={<DocumentRagRunner />} />
        <Route path="/workflow" element={<WorkflowManager />} />
      </Route>
    </Routes>
  );
}

export default App
