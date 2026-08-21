import React from 'react';
import { useNavigate } from 'react-router-dom';

export default function LandingPage() {

  const navigate = useNavigate();
  return (
    <div className="bg-surface font-body-lg text-on-surface min-h-screen">
      {/* Header */}
      <header className="fixed top-0 w-full z-50 bg-surface/80 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
        <div className="h-16 w-full px-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img 
              alt="Waraq logo" 
              className="h-8 w-auto object-contain" 
              src="/waraq.png" 
            />
            <span className="font-semibold text-xl text-on-surface tracking-tight">Waraq</span>
          </div>
          <nav className="hidden md:flex items-center gap-6">
            <a className="transition-colors text-primary font-semibold" href="#product">Product</a>
            <a className="text-sm text-on-surface-variant hover:text-on-surface transition-colors" href="#solutions">Solutions</a>
            <a className="text-sm text-on-surface-variant hover:text-on-surface transition-colors" href="#pricing">Pricing</a>
          </nav>
          <div className="flex items-center gap-2">
            <a className="px-4 py-1 text-sm text-on-surface hover:text-primary transition-colors" href="/login">Login</a>
            <a className="bg-primary text-on-primary px-6 py-2 rounded-xl text-sm hover:bg-primary-container transition-all" href="/register">Get Started</a>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="w-full pt-16">
        <div className="flex flex-col w-full relative overflow-hidden bg-surface">
          
          {/* Hero Section */}
          <section className="relative w-full pt-[120px] pb-8 lg:pt-[160px] lg:pb-[120px] px-6 flex flex-col lg:flex-row items-center gap-6 z-10">
            {/* Background Gradients */}
            <div className="absolute inset-0 pointer-events-none overflow-hidden -z-10">
              <div className="absolute top-[-10%] right-[-5%] w-[600px] h-[600px] bg-tertiary-fixed opacity-40 rounded-full blur-[120px] mix-blend-multiply" />
              <div className="absolute bottom-[-20%] left-[-10%] w-[400px] h-[400px] bg-primary-fixed opacity-20 rounded-full blur-[100px]" />
            </div>

            <div className="flex-1 flex flex-col gap-2 z-10 max-w-2xl">
              <div className="inline-flex items-center gap-1 bg-surface-container-high px-3 py-1 rounded-full w-fit mb-4">
                <span className="material-symbols-outlined text-[14px] text-primary">auto_awesome</span>
                <span className="text-[11px] font-bold text-on-surface uppercase tracking-wider">Propulsé par Qwen 2.5 Local LLM</span>
              </div>
              
              <h1 className="text-3xl lg:text-[56px] lg:leading-[64px] font-semibold text-on-surface tracking-tight">
                Automatisez votre réponse aux <span className="text-primary relative inline-block">Marchés Publics<span className="absolute bottom-2 left-0 w-full h-[8px] bg-tertiary-fixed-dim/50 -z-10 skew-x-[-15deg]" /></span> avec l'IA
              </h1>
              
              <p className="text-lg text-on-surface-variant mt-4 max-w-xl">
                Waraq utilise l'IDP et le RAG pour scraper, classifier et générer vos dossiers de candidature en un temps record. Une solution sécurisée et sur-mesure pour le marché marocain.
              </p>

              <div className="flex flex-wrap items-center gap-4 mt-8">
                <a className="bg-primary text-on-primary px-8 py-4 rounded-xl font-semibold text-base hover:bg-primary-container transition-all hover:-translate-y-1 shadow-[0_8px_16px_rgba(170,0,3,0.2)] flex items-center gap-2" href="/register">
                  Commencer Gratuitement
                  <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                </a>
            </div>

              {/* Trust Badges */}
              <div className="flex items-center gap-4 mt-8 pt-6 border-t border-outline-variant/30">
                <div className="flex -space-x-3">
                  <img className="w-10 h-10 rounded-full border-2 border-surface object-cover" alt="User 1" src="https://lh3.googleusercontent.com/aida-public/AB6AXuBXa3mw9seuwzNPdU4ckByyyXtwtfaUzL8ozOkRA5pNl2IxoHE90F7HV_8tvmTHy-6tGx-fWKaqllzefCnPDqGm7Vz96XFIWo5xblSuJtnGY7ZR4eQY__78R-0stF4YOAdWuJ809vRPf2DeNZ0MyFFFaqo0vvHtEMten_MjJV-yTc035gbn2Me6qQ0j6yUCKjn0SraJSY8hAFwmzi2xYL9ZjhvhIKf5pA01VraV6bgPV_TeVfNpL7hjiw" />
                  <img className="w-10 h-10 rounded-full border-2 border-surface object-cover" alt="User 2" src="https://lh3.googleusercontent.com/aida-public/AB6AXuDkyf9EbK__FvCIMADJdIXOvcd8Ur8GHaT_7Vw2-MM0HfutQIs9-5IdfoaQkk0qRWZw20dLdm3nr6OeXaLBC2qdkYmlmd4yM6tBqRMQT9S7Eo_kTe9RwyI7fhYPEVa6q2b35iNmrPG5qx3vg76GYkxg6w52jnGc0pDISaLiZw_3bfIHiTdk9gZGtcxhNSXZ8RCmBzh6y70_ho-VWDW0d-dp0T2Zt4kgFt5SKAgfCv6ZpXH7X7dakly8wg" />
                  <img className="w-10 h-10 rounded-full border-2 border-surface object-cover" alt="User 3" src="https://lh3.googleusercontent.com/aida-public/AB6AXuAk0CBatVil662YrBfFEk4lCHYVY-FqhD3JxQGaQQca-r1W07N2co5iLGSO9iBYZsaTfUwBLKmT3E3TWXKGvn7qyV4e7EpcKCJR--wghxgIFoOo4WAWe5uIE-zDGjmFBfgAFb1-qvJQ64y_LJMVkSHN2q_iqbiiH7axOSkD_6pGqOuurzJg9VFt5oBGG8hke1nLJ7q-c-eAKq4UblBh_26iFu195KkCd8OOrMOgnm27FM0FZ8vOUfiZQg" />
                </div>
                <div className="flex flex-col">
                  <div className="flex items-center gap-1 text-[#F59E0B]">
                    {[...Array(5)].map((_, i) => (
                      <span key={i} className="material-symbols-outlined text-[16px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
                    ))}
                  </div>
                  <span className="text-xs text-on-surface-variant">Rejoint par +150 entreprises marocaines</span>
                </div>
              </div>
            </div>

            {/* Dashboard Mockup */}
            <div className="flex-1 relative w-full h-full min-h-[400px] lg:min-h-[600px] flex items-center justify-center">
                {/* Card / Window Container */}
                <div className="relative w-full max-w-[600px] aspect-[4/3] bg-surface-container rounded-2xl shadow-xl overflow-hidden border border-outline-variant group flex flex-col">
                    
                    {/* macOS Window Header */}
                    <div className="h-8 bg-surface-container-highest border-b border-outline-variant flex items-center px-4 gap-2 shrink-0 z-10">
                    <div className="w-3 h-3 rounded-full bg-error" />
                    <div className="w-3 h-3 rounded-full bg-[#F59E0B]" />
                    <div className="w-3 h-3 rounded-full bg-[#10B981]" />
                    </div>

                    {/* Video Container (Replaces internal mockup) */}
                    <div className="relative flex-1 w-full bg-black overflow-hidden">
                    <video
                        src="/demo.mp4"
                        autoPlay
                        loop
                        muted
                        playsInline
                        className="w-full h-full object-cover"
                    />
                    
                    {/* Subtle top/bottom gradient overlay to blend smoothly */}
                    <div className="absolute inset-0 pointer-events-none bg-gradient-to-b from-black/10 via-transparent to-black/20" />
                    </div>
                </div>
                </div>
          </section>

          {/* Bento Grid Features */}
          <section className="w-full py-[100px] px-6 bg-surface relative">
            <div className="max-w-7xl mx-auto flex flex-col gap-6">
              <div className="flex flex-col md:flex-row justify-between items-end gap-6 mb-8">
                <div className="max-w-2xl">
                  <h2 className="text-3xl font-semibold text-on-surface">La suite complète pour dominer les Appels d'Offres.</h2>
                  <p className="text-lg text-on-surface-variant mt-4">Ne perdez plus des heures sur des tâches administratives répétitives. Notre pipeline IA gère tout, de la détection à la génération finale.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Feature 1 */}
                <div className="md:col-span-2 bg-surface-container rounded-2xl p-6 lg:p-8 flex flex-col justify-between border border-outline-variant relative overflow-hidden group hover:bg-surface-container-high transition-colors">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-tertiary-fixed opacity-30 blur-[60px] rounded-full translate-x-1/2 -translate-y-1/2" />
                  <div className="z-10 max-w-md">
                    <div className="w-12 h-12 rounded-xl bg-surface border border-outline-variant flex items-center justify-center mb-6">
                      <span className="material-symbols-outlined text-on-surface">travel_explore</span>
                    </div>
                    <h3 className="text-xl font-semibold text-on-surface">Scraper Intelligent</h3>
                    <p className="text-sm text-on-surface-variant mt-2">Surveillance automatisée du portail des Marchés Publics marocains. Recevez des alertes pertinentes basées sur vos critères métier.</p>
                  </div>
                  <div className="mt-8 bg-surface rounded-xl border border-outline-variant p-4 h-40 relative overflow-hidden flex items-end">
                    <div className="w-full font-mono text-[10px] leading-tight text-on-surface-variant opacity-70 absolute top-4 left-4">
                      &gt; INITIALIZING CRAWLER_V2<br />
                      &gt; TARGET: marchespublics.gov.ma<br />
                      &gt; FILTER: "Génie Civil", "Grand Casablanca"<br />
                      &gt; FOUND: 3 NEW OPPORTUNITIES<br />
                      <span className="text-primary">&gt; EXTRACTING METADATA...</span>
                    </div>
                    <div className="w-full h-8 bg-tertiary-fixed-dim/20 rounded border border-tertiary-fixed flex items-center px-2 mt-auto z-10 backdrop-blur-sm">
                      <span className="w-2 h-2 rounded-full bg-[#10B981] mr-2" />
                      <span className="text-xs text-on-surface">Extraction Réussie : AO N° 45/2024</span>
                    </div>
                  </div>
                </div>

                {/* Feature 2 */}
                <div className="bg-primary text-on-primary rounded-2xl p-6 lg:p-8 flex flex-col justify-between relative overflow-hidden shadow-xl hover:-translate-y-1 transition-transform">
                  <div className="z-10">
                    <div className="w-12 h-12 rounded-xl bg-on-primary/10 border border-on-primary/20 flex items-center justify-center mb-6">
                      <span className="material-symbols-outlined text-on-primary">document_scanner</span>
                    </div>
                    <h3 className="text-xl font-semibold">Classification IDP</h3>
                    <p className="text-sm text-on-primary/80 mt-2">Notre modèle identifie et sépare automatiquement les CPS, RC, BDP et plans techniques à partir d'archives ZIP chaotiques.</p>
                  </div>
                  <div className="mt-8 flex flex-col gap-2 z-10">
                    <div className="bg-on-primary/10 rounded-lg p-2 flex items-center gap-2 border border-on-primary/20">
                      <span className="material-symbols-outlined text-[16px]">folder_zip</span>
                      <span className="font-mono text-xs truncate">Dossier_AO_45.zip</span>
                    </div>
                    <div className="flex flex-col gap-1 pl-4 border-l border-on-primary/30 ml-2">
                      <div className="flex items-center gap-2">
                        <span className="w-4 border-t border-on-primary/30" />
                        <span className="text-xs bg-on-primary/20 px-2 py-1 rounded">CPS</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="w-4 border-t border-on-primary/30" />
                        <span className="text-xs bg-on-primary/20 px-2 py-1 rounded">Bordereau (BDP)</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Feature 3 */}
                <div className="bg-surface-container rounded-2xl p-6 lg:p-8 border border-outline-variant flex flex-col hover:bg-surface-container-high transition-colors">
                  <div className="w-12 h-12 rounded-xl bg-surface border border-outline-variant flex items-center justify-center mb-6">
                    <span className="material-symbols-outlined text-on-surface">supervised_user_circle</span>
                  </div>
                  <h3 className="text-xl font-semibold text-on-surface">Validation Humaine</h3>
                  <p className="text-sm text-on-surface-variant mt-2 mb-6">L'IA prépare, vous validez. Gardez le contrôle total grâce à notre interface de vérification intuitive (Human-in-the-Loop).</p>
                  <div className="mt-auto bg-surface rounded-xl border border-outline-variant p-3 flex flex-col gap-3">
                    <div className="flex justify-between items-center pb-2 border-b border-outline-variant/50">
                      <span className="text-xs text-on-surface-variant">Garantie Provisoire</span>
                      <span className="font-mono text-xs font-bold text-on-surface">50,000 MAD</span>
                    </div>
                    <div className="flex gap-2">
                      <button className="flex-1 bg-surface-container-low border border-outline-variant rounded py-1 text-xs text-on-surface hover:bg-error-container hover:text-on-error-container transition-colors">Corriger</button>
                      <button className="flex-1 bg-tertiary-fixed text-on-tertiary-fixed rounded py-1 text-xs hover:bg-tertiary-fixed-dim transition-colors flex items-center justify-center gap-1">
                        <span className="material-symbols-outlined text-[14px]">check</span> Valider
                      </button>
                    </div>
                  </div>
                </div>

                {/* Feature 4 */}
                <div className="md:col-span-2 bg-tertiary-fixed rounded-2xl p-6 lg:p-8 flex flex-col md:flex-row items-center gap-8 overflow-hidden relative shadow-sm border border-tertiary-fixed-dim">
                  <div className="flex-1 z-10">
                    <div className="w-12 h-12 rounded-xl bg-surface border border-outline-variant flex items-center justify-center mb-6">
                      <span className="material-symbols-outlined text-on-surface">description</span>
                    </div>
                    <h3 className="text-xl font-semibold text-on-tertiary-fixed">Génération de Documents</h3>
                    <p className="text-sm text-on-tertiary-fixed-variant mt-2">Exportez des dossiers de candidature complets (Déclaration sur l'honneur, Acte d'engagement) pré-remplis au format Word (.docx), prêts à être signés.</p>
                    <div className="mt-6 flex items-center gap-4">
                      <span className="font-mono text-xs bg-surface/50 px-3 py-1 rounded-full text-on-tertiary-fixed-variant border border-tertiary-fixed-dim">.docx</span>
                      <span className="font-mono text-xs bg-surface/50 px-3 py-1 rounded-full text-on-tertiary-fixed-variant border border-tertiary-fixed-dim">.pdf</span>
                      <span className="font-mono text-xs bg-surface/50 px-3 py-1 rounded-full text-on-tertiary-fixed-variant border border-tertiary-fixed-dim">.xlsx</span>
                    </div>
                  </div>
                  <div className="flex-1 w-full h-full min-h-[200px] relative">
                    <div 
                      className="absolute inset-0 bg-cover bg-center rounded-xl shadow-md border border-white/40" 
                      style={{ backgroundImage: "url('https://lh3.googleusercontent.com/aida-public/AB6AXuDuQdrWPyfofPtTG64rMZ5Feo2UqkrFp2C3NrrPBp2wGTsGYveZi8cGrY4cBBHx2p87Z6ky-cmvMhV6hD7PE6hz_jt5cou-hWZAGT8lArGu8CXGgGAaiUScy-ifqjG7ARDRKMruNKMFhlO8_Jkcuf5x6oppRNCP8_gdXMrtzaaCS3RZbPBiGr_14WGB8XnDU_8UlAEeqG54ik5PPsLCh9JIARO4Gm7Os7iOYprWi3wkcuoqBeDrwCBPAA')" }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Architecture / Security Section */}
          <section className="w-full py-[100px] px-6 bg-inverse-surface text-inverse-on-surface relative overflow-hidden">
            <div className="max-w-5xl mx-auto text-center flex flex-col items-center gap-6 z-10 relative">
              <span className="font-mono text-xs text-primary-fixed-dim bg-primary/20 px-3 py-1 rounded-full border border-primary/30">ARCHITECTURE SÉCURISÉE</span>
              <h2 className="text-3xl lg:text-[40px] font-semibold leading-tight max-w-3xl">Vos données stratégiques ne quittent jamais l'environnement de travail.</h2>
              <p className="text-lg text-surface-variant max-w-2xl">
                Déployé avec le modèle <strong>Qwen 2.5</strong> en local, Waraq garantit une confidentialité absolue de vos documents financiers et techniques. Aucune donnée n'est envoyée vers des API tierces externes.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-12 w-full text-left">
                <div className="flex flex-col gap-3 p-6 border-t border-surface-variant/20">
                  <span className="material-symbols-outlined text-[32px] text-primary-fixed">speed</span>
                  <h4 className="font-semibold text-lg">Efficacité Maximale</h4>
                  <p className="text-sm text-surface-variant opacity-80">Réduction de 70% du temps passé sur le montage des dossiers.</p>
                </div>
                <div className="flex flex-col gap-3 p-6 border-t border-surface-variant/20">
                  <span className="material-symbols-outlined text-[32px] text-tertiary-fixed">gavel</span>
                  <h4 className="font-semibold text-lg">Conformité Totale</h4>
                  <p className="text-sm text-surface-variant opacity-80">Règles métier marocaines intégrées nativement dans le moteur d'inférence.</p>
                </div>
                <div className="flex flex-col gap-3 p-6 border-t border-surface-variant/20">
                  <span className="material-symbols-outlined text-[32px] text-[#10B981]">shield_locked</span>
                  <h4 className="font-semibold text-lg">Sécurité Local LLM</h4>
                  <p className="text-sm text-surface-variant opacity-80">Traitement on-premise ou cloud souverain sans exposition des données.</p>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full bg-surface-container-low border-t border-outline-variant py-6">
        <div className="w-full px-6 flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2">
            <img 
              alt="Waraq logo" 
              className="h-5 w-auto grayscale opacity-50" 
              src="/logo.png" 
            />
            <span className="text-xs text-on-surface-variant">© 2024 Waraq Intelligent Document Processing.</span>
          </div>
          <div className="flex gap-6">
            <a className="text-xs text-on-surface-variant hover:text-primary" href="#privacy">Privacy</a>
            <a className="text-xs text-on-surface-variant hover:text-primary" href="#terms">Terms</a>
            <a className="text-xs text-on-surface-variant hover:text-primary" href="#security">Security</a>
          </div>
        </div>
      </footer>
    </div>
  );
}