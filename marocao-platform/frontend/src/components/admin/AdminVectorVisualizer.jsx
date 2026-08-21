import React, { useState, useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { useAuth } from '../../context/AuthContext';

export default function AdminVectorVisualizer3D() {
  const { fetchWithAuth } = useAuth();
  const mountRef = useRef(null);

  // Mode & Filtres
  const [searchMode, setSearchMode] = useState('tender');
  const [targetId, setTargetId] = useState('');
  const [maxPoints, setMaxPoints] = useState(200);
  const [reductionMethod, setReductionMethod] = useState('tsne');

  // États de chargement et données
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [vectorData, setVectorData] = useState(null);
  const [selectedPoint, setSelectedPoint] = useState(null);

  // Modal Lookup UUID avec Pagination
  const [showLookupModal, setShowLookupModal] = useState(false);
  const [lookupItems, setLookupItems] = useState([]);
  const [lookupFilter, setLookupFilter] = useState('');
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupPage, setLookupPage] = useState(1);
  const [lookupTotalPages, setLookupTotalPages] = useState(1);
  const [lookupTotalCount, setLookupTotalCount] = useState(0);

  // Handlers
  const handleFilterChange = (e) => {
    setLookupFilter(e.target.value);
    setLookupPage(1);
  };

  const handleModeChange = (e) => {
    setSearchMode(e.target.value);
    setTargetId('');
    setLookupPage(1);
    setLookupFilter('');
  };

  // Chargement des UUIDs paginés
  useEffect(() => {
    if (!showLookupModal) return;

    const fetchLookupData = async () => {
      setLookupLoading(true);
      try {
        const endpoint =
          searchMode === 'tender'
            ? `/api/rag/vectors/lookup/tenders?query=${encodeURIComponent(lookupFilter)}&page=${lookupPage}&page_size=10`
            : `/api/rag/vectors/lookup/documents?query=${encodeURIComponent(lookupFilter)}&page=${lookupPage}&page_size=10`;

        const response = await fetchWithAuth(endpoint);
        if (response.ok) {
          const data = await response.json();
          setLookupItems(data.items || []);
          setLookupTotalPages(data.total_pages || 1);
          setLookupTotalCount(data.total || 0);
        }
      } catch (err) {
        console.error("Erreur lors de la recherche des UUIDs:", err);
      } finally {
        setLookupLoading(false);
      }
    };

    const timer = setTimeout(fetchLookupData, 300);
    return () => clearTimeout(timer);
  }, [showLookupModal, lookupFilter, lookupPage, searchMode, fetchWithAuth]);

  // Appel principal à l'API RAG
  const handleFetchVectors = async (e) => {
  e.preventDefault();
  if (!targetId.trim()) return;

  setLoading(true);
  setError(null);
  setSelectedPoint(null);

  const endpoint =
    searchMode === 'tender'
      ? `/api/rag/vectors/tender/${targetId.trim()}?max_points=${maxPoints}&method=${reductionMethod}`
      : `/api/rag/vectors/document/${targetId.trim()}?max_points=${maxPoints}&method=${reductionMethod}`;

  try {
    const response = await fetchWithAuth(endpoint);
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Erreur lors de la récupération des vecteurs');
    }
    const data = await response.json();
    setVectorData(data);
  } catch (err) {
    console.error(err);
    setError(err.message);
    setVectorData(null);
  } finally {
    setLoading(false);
  }
};

  // --- MOTEUR THREE.JS (Fond Rouge & Sphères/Liens Blancs) ---
  useEffect(() => {
    if (!vectorData || !vectorData.points || vectorData.points.length === 0 || !mountRef.current) return;

    const container = mountRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
    camera.position.set(0, 0, 10);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setClearColor(0x7f1d1d, 1); // Fond rouge bordeaux profond
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    const pointsGroup = new THREE.Group();

    // Normalisation des coordonnées réelles (-5 à 5)
    const points = vectorData.points;
    const xs = points.map((p) => p.x ?? p.coordinates?.[0] ?? 0);
    const ys = points.map((p) => p.y ?? p.coordinates?.[1] ?? 0);
    const zs = points.map((p) => p.z ?? p.coordinates?.[2] ?? 0);

    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const minZ = Math.min(...zs), maxZ = Math.max(...zs);

    const normalize = (val, min, max) => (max === min ? 0 : ((val - min) / (max - min) - 0.5) * 10);

    // Sphères blanches lumineuses
    const sphereGeometry = new THREE.SphereGeometry(0.13, 16, 16);
    const defaultMaterial = new THREE.MeshPhongMaterial({
      color: 0xffffff,
      emissive: 0xe2e8f0,
      emissiveIntensity: 0.6,
      shininess: 100,
    });

    const meshes = [];

    // Remplacement du mapping des coordonnées Three.js
points.forEach((p, idx) => {
  const isSelected = selectedPoint && selectedPoint.id === p.id;
  const mat = isSelected
    ? new THREE.MeshPhongMaterial({
        color: 0xfef08a,
        emissive: 0xeab308,
        emissiveIntensity: 1.0,
      })
    : defaultMaterial;

  const mesh = new THREE.Mesh(sphereGeometry, mat);

  // Utilisation directe des coordonnées 3D préparées par le backend
  const posX = p.x ?? p.coordinates?.[0] ?? 0;
  const posY = p.y ?? p.coordinates?.[1] ?? 0;
  const posZ = p.z ?? p.coordinates?.[2] ?? 0;

  mesh.position.set(posX, posY, posZ);

  mesh.userData = { ...p, index: idx };
  meshes.push(mesh);
  pointsGroup.add(mesh);
});

    scene.add(pointsGroup);

    // Lignes de connexions blanches semi-transparentes
    const lineMaterial = new THREE.LineBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.25,
    });

    const maxConnections = Math.min(points.length * 2, 150);
    for (let i = 0; i < maxConnections; i++) {
      const idx1 = Math.floor(Math.random() * meshes.length);
      const idx2 = Math.floor(Math.random() * meshes.length);

      if (idx1 !== idx2) {
        const p1 = meshes[idx1].position;
        const p2 = meshes[idx2].position;

        if (p1.distanceTo(p2) < 4.0) {
          const lineGeometry = new THREE.BufferGeometry().setFromPoints([p1, p2]);
          const line = new THREE.Line(lineGeometry, lineMaterial);
          pointsGroup.add(line);
        }
      }
    }

    // Éclairage blanc éclatant
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(0xffffff, 1.2);
    pointLight.position.set(8, 8, 8);
    scene.add(pointLight);

    // Interaction souris (Parallaxe spatial)
    let mouseX = 0;
    let mouseY = 0;

    const handleMouseMove = (event) => {
      const rect = container.getBoundingClientRect();
      mouseX = ((event.clientX - rect.left) / width) - 0.5;
      mouseY = ((event.clientY - rect.top) / height) - 0.5;
    };

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const handleClick = (event) => {
      const rect = container.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(meshes);

      if (intersects.length > 0) {
        const clickedData = intersects[0].object.userData;
        setSelectedPoint(clickedData);
      }
    };

    container.addEventListener('mousemove', handleMouseMove);
    container.addEventListener('click', handleClick);

    const handleResize = () => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    // Animation de rotation spatiale + réactivité souris
    let animationFrameId;
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      pointsGroup.rotation.y += 0.002;
      pointsGroup.rotation.x += 0.001;

      pointsGroup.position.x += (mouseX * 2 - pointsGroup.position.x) * 0.05;
      pointsGroup.position.y += (-mouseY * 2 - pointsGroup.position.y) * 0.05;

      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      container.removeEventListener('mousemove', handleMouseMove);
      container.removeEventListener('click', handleClick);
      window.removeEventListener('resize', handleResize);
      controls.dispose();
      if (renderer.domElement) container.removeChild(renderer.domElement);
    };
  }, [vectorData, selectedPoint]);

  return (
    <div className="p-6 max-w-7xl mx-auto flex flex-col gap-6">
      {/* Titre */}
      <div>
        <h1 className="text-2xl font-bold text-on-surface">Visualisateur 3D RAG</h1>
        <p className="text-sm text-on-surface-variant">
          Exploration interactive des vecteurs et embeddings
        </p>
      </div>

      {/* Formulaire de Sélection */}
      <form onSubmit={handleFetchVectors} className="bg-surface-container-lowest p-5 rounded-xl border border-outline-variant/30 shadow-sm flex flex-col md:flex-row gap-4 items-end">
        <div className="flex flex-col gap-1.5 w-full md:w-48">
          <label className="text-xs font-semibold text-on-surface-variant">Type d'entité</label>
          <select
            value={searchMode}
            onChange={handleModeChange}
            className="px-3 py-2 bg-surface-container-low border border-outline-variant/40 rounded-lg text-sm text-on-surface focus:outline-none"
          >
            <option value="tender">Tender ID</option>
            <option value="document">Document ID</option>
          </select>
        </div>

        <div className="flex flex-col gap-1.5 flex-1 w-full">
          <div className="flex justify-between items-center">
            <label className="text-xs font-semibold text-on-surface-variant">
              {searchMode === 'tender' ? 'UUID du Tender' : 'UUID du Document'}
            </label>
            <button
              type="button"
              onClick={() => setShowLookupModal(true)}
              className="text-xs text-primary hover:underline flex items-center gap-1 font-medium"
            >
              <span className="material-symbols-outlined text-sm">search</span>
              Sélectionner un UUID
            </button>
          </div>
          <input
            type="text"
            required
            placeholder="Ex: 123e4567-e89b-12d3-a456-426614174000"
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            className="px-3 py-2 bg-surface-container-low border border-outline-variant/40 rounded-lg text-sm text-on-surface font-mono text-xs focus:outline-none"
          />
        </div>

        <div className="flex flex-col gap-1.5 w-full md:w-32">
          <label className="text-xs font-semibold text-on-surface-variant">Max Points</label>
          <input
            type="number"
            min="10"
            max="1000"
            value={maxPoints}
            onChange={(e) => setMaxPoints(Number(e.target.value))}
            className="px-3 py-2 bg-surface-container-low border border-outline-variant/40 rounded-lg text-sm text-on-surface focus:outline-none"
          />
        </div>
        {/* Selecteur de méthode de réduction dimensionnelle */}
<div className="flex flex-col gap-1.5 w-full md:w-36">
  <label className="text-xs font-semibold text-on-surface-variant">Algorithme</label>
  <select
    value={reductionMethod}
    onChange={(e) => setReductionMethod(e.target.value)}
    className="px-3 py-2 bg-surface-container-low border border-outline-variant/40 rounded-lg text-sm text-on-surface focus:outline-none"
  >
    <option value="tsne">t-SNE (3D)</option>
    <option value="pca">PCA (3D)</option>
  </select>
</div>

        <button
          type="submit"
          disabled={loading}
          className="flex items-center justify-center gap-2 px-5 py-2 bg-primary text-on-primary rounded-lg text-sm font-medium shadow-sm hover:opacity-90 disabled:opacity-50 transition-all w-full md:w-auto"
        >
          <span className={`material-symbols-outlined text-lg ${loading ? 'animate-spin' : ''}`}>
            {loading ? 'sync' : '3d_rotation'}
          </span>
          {loading ? 'Chargement...' : 'Générer 3D'}
        </button>
      </form>

      {/* Message d'Erreur */}
      {error && (
        <div className="p-4 bg-error-container/20 border border-error/30 rounded-xl flex items-center gap-3 text-error text-sm">
          <span className="material-symbols-outlined text-xl">error</span>
          <span>{error}</span>
        </div>
      )}

      {/* Canvas Three.js & Détails */}
      {vectorData && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 flex flex-col gap-4">
            <div className="w-full h-[520px] rounded-2xl overflow-hidden relative shadow-md border border-red-900/40">
              <div ref={mountRef} className="w-full h-full cursor-grab active:cursor-grabbing" />
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="bg-surface-container-lowest p-3 rounded-xl border border-outline-variant/20 text-center">
                <span className="text-[11px] text-on-surface-variant font-medium uppercase">Référence</span>
                <p className="text-sm font-bold text-on-surface truncate mt-0.5">
                  {vectorData.tender_reference || vectorData.reference || '-'}
                </p>
              </div>
              <div className="bg-surface-container-lowest p-3 rounded-xl border border-outline-variant/20 text-center">
                <span className="text-[11px] text-on-surface-variant font-medium uppercase">Total Points</span>
                <p className="text-sm font-bold text-primary mt-0.5">
                  {vectorData.points?.length || 0}
                </p>
              </div>
              <div className="bg-surface-container-lowest p-3 rounded-xl border border-outline-variant/20 text-center">
                <span className="text-[11px] text-on-surface-variant font-medium uppercase">Moteur</span>
                <p className="text-sm font-bold text-secondary mt-0.5">Three.js</p>
              </div>
              <div className="bg-surface-container-lowest p-3 rounded-xl border border-outline-variant/20 text-center">
  <span className="text-[11px] text-on-surface-variant font-medium uppercase">Algorithme</span>
  <p className="text-sm font-bold text-secondary uppercase mt-0.5">
    {vectorData.method_used || reductionMethod}
  </p>
</div>
            </div>
          </div>

          {/* Inspection du point sélectionné */}
<div className="bg-surface-container-lowest p-5 rounded-xl border border-outline-variant/30 shadow-sm flex flex-col h-full min-h-0">
  <h3 className="text-sm font-bold text-on-surface flex items-center gap-2 border-b border-outline-variant/20 pb-2 shrink-0">
    <span className="material-symbols-outlined text-primary text-lg">info</span>
    Inspection du Chunk
  </h3>

  {selectedPoint ? (
    <div className="flex flex-col gap-3 text-xs flex-1 min-h-0 mt-3">
      <div className="shrink-0">
        <span className="font-semibold text-on-surface-variant">ID Vectoriel :</span>
        <p className="font-mono text-on-surface bg-surface-container-low p-1.5 rounded mt-0.5 truncate">
          {selectedPoint.id}
        </p>
      </div>

      {selectedPoint.metadata && (
        <div className="shrink-0">
          <span className="font-semibold text-on-surface-variant">Métadonnées :</span>
          <pre className="bg-surface-container-low p-2 rounded text-[11px] font-mono overflow-x-auto text-on-surface border border-outline-variant/20 mt-0.5 max-h-24">
            {JSON.stringify(selectedPoint.metadata, null, 2)}
          </pre>
        </div>
      )}

      {/* Conteneur du texte qui s'étire exactement jusqu'en bas */}
      <div className="flex flex-col flex-1 min-h-0">
        <span className="font-semibold text-on-surface-variant mb-1 shrink-0">Contenu du Texte :</span>
        <div className="relative flex-1 w-full min-h-0">
          <div className="absolute inset-0 bg-surface-container-low p-3 rounded-lg text-on-surface leading-relaxed overflow-y-auto border border-outline-variant/20 whitespace-pre-wrap font-sans text-xs">
            {selectedPoint.document || selectedPoint.text || selectedPoint.content || 'Aucun contenu textuel.'}
          </div>
        </div>
      </div>
    </div>
  ) : (
    <div className="flex flex-col items-center justify-center flex-1 text-center text-on-surface-variant/60">
      <span className="material-symbols-outlined text-3xl mb-2">touch_app</span>
      <p className="text-xs">Cliquez sur une sphère pour inspecter son extrait.</p>
    </div>
  )}
</div>
        </div>
      )}

      {/* Modal Assistant UUID avec Pagination */}
      {showLookupModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-surface-container-lowest border border-outline-variant/30 rounded-2xl w-full max-w-lg shadow-xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="p-4 border-b border-outline-variant/20 flex justify-between items-center">
              <div>
                <h3 className="font-semibold text-sm text-on-surface">
                  Sélectionner un {searchMode === 'tender' ? 'Tender' : 'Document'}
                </h3>
                <p className="text-[11px] text-on-surface-variant">
                  {lookupTotalCount} résultat(s) disponible(s)
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowLookupModal(false)}
                className="text-on-surface-variant hover:text-on-surface"
              >
                <span className="material-symbols-outlined text-xl">close</span>
              </button>
            </div>

            <div className="p-4 border-b border-outline-variant/10">
              <input
                type="text"
                placeholder="Filtrer par référence ou nom..."
                value={lookupFilter}
                onChange={handleFilterChange}
                className="w-full px-3 py-2 bg-surface-container-low border border-outline-variant/30 rounded-lg text-sm text-on-surface focus:outline-none"
              />
            </div>

            <div className="p-2 overflow-y-auto flex-1 flex flex-col gap-1 min-h-[280px]">
              {lookupLoading ? (
                <div className="p-6 text-center text-xs text-on-surface-variant">Chargement...</div>
              ) : lookupItems.length === 0 ? (
                <div className="p-6 text-center text-xs text-on-surface-variant">Aucun résultat</div>
              ) : (
                lookupItems.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setTargetId(item.id);
                      setShowLookupModal(false);
                    }}
                    className="p-3 text-left hover:bg-surface-container-low rounded-lg transition-colors flex flex-col gap-0.5 border border-transparent hover:border-outline-variant/20"
                  >
                    <div className="flex justify-between items-center">
                      <span className="font-semibold text-xs text-on-surface">
                        {item.reference || item.filename}
                      </span>
                      <span className="text-[10px] text-primary font-mono bg-primary/10 px-1.5 py-0.5 rounded">
                        Sélectionner
                      </span>
                    </div>
                    <span className="text-[11px] text-on-surface-variant font-mono truncate">
                      {item.id}
                    </span>
                  </button>
                ))
              )}
            </div>

            {/* Pagination Controls */}
            <div className="p-3 border-t border-outline-variant/20 flex items-center justify-between bg-surface-container-low/50">
              <span className="text-xs text-on-surface-variant">
                Page <strong>{lookupPage}</strong> sur <strong>{lookupTotalPages}</strong>
              </span>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={lookupPage <= 1 || lookupLoading}
                  onClick={() => setLookupPage((prev) => Math.max(prev - 1, 1))}
                  className="px-3 py-1 bg-surface-container border border-outline-variant/30 rounded text-xs text-on-surface disabled:opacity-40 hover:bg-surface-container-high transition-all flex items-center gap-1"
                >
                  <span className="material-symbols-outlined text-sm">chevron_left</span>
                  Précédent
                </button>
                <button
                  type="button"
                  disabled={lookupPage >= lookupTotalPages || lookupLoading}
                  onClick={() => setLookupPage((prev) => Math.min(prev + 1, lookupTotalPages))}
                  className="px-3 py-1 bg-surface-container border border-outline-variant/30 rounded text-xs text-on-surface disabled:opacity-40 hover:bg-surface-container-high transition-all flex items-center gap-1"
                >
                  Suivant
                  <span className="material-symbols-outlined text-sm">chevron_right</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}