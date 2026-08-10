# Rapport Technique — Pipeline RAG de Waraq
### Module d'analyse métier des dossiers d'appels d'offres (rag_engine)

---

## 1. Objectif du document

Ce rapport décrit et explique en détail le **pipeline RAG** (Retrieval-Augmented Generation) intégré à Waraq, qui vient compléter la classification automatique (Qwen) déjà en place. Il couvre :

- l'évolution de l'architecture entre le schéma initial et le schéma modifié ;
- le rôle précis de chaque fichier du module `rag_engine` ;
- l'organisation du stockage disque associée ;
- les points forts de la conception ;
- quelques incohérences techniques relevées dans le code actuel, utiles à corriger ou à clarifier avant la mise en production.

---

## 2. Contexte : de la classification à l'analyse métier

La classification (Qwen + PyMuPDF + RapidOCR) répond à une question simple : **« quel type de document est-ce ? »** (RC, CPS, BDP, Acte d'Engagement…).

Le pipeline RAG répond à une question plus riche : **« qu'est-ce que ce document dit, concrètement, et comment l'exploiter pour préparer une soumission ? »** — objet du marché, dates limites, pièces à fournir, critères d'évaluation, pénalités, garanties, etc.

C'est un changement de nature, pas seulement d'échelle : on passe d'une tâche de **catégorisation** à une tâche d'**extraction d'information structurée**, ce qui justifie un pipeline dédié, découplé de la chaîne de classification.

---

## 3. Comparaison des deux architectures

### 3.1 Schéma initial

```
Document → Classification (Qwen) → GLM-OCR → Granite 4.1:3B
         → extracted_text enrichi → BGE Embedding → ChromaDB → Recherche RAG
```

Dans cette première version, le RAG **réutilise** le champ `extracted_text` déjà produit pendant la classification (PyMuPDF + RapidOCR), sans ré-extraction. C'est d'ailleurs ce que décrit ton paragraphe descriptif : *« Ce pipeline exploite le texte intégral déjà extrait par RapidOCR ONNX et stocké dans le champ `extracted_text`, sans nécessiter une nouvelle extraction OCR »*.

### 3.2 Schéma modifié (implémenté dans le code fourni)

```
Classification Qwen → Déclenchement RAG asynchrone → Extracteur RAG indépendant
→ Détection des documents internes → Dossier extracted/ → GLM-OCR
→ DocumentChunker → BGE-M3 → ChromaDB → Recherche sémantique → Granite 4.1:3B
→ rag_analysis (JSON)
```

Ici, le RAG **ne réutilise plus** `extracted_text`. C'est explicitement indiqué dans `rag_service.py` :

> *« Ce texte provient exclusivement de l'extracteur RAG. On ne lit PAS `doc.extracted_text` ici. »*

À la place, `rag_document_extractor.py` ré-exécute sa **propre** extraction (PyMuPDF + RapidOCR + détection de qualité OCR), indépendante du `learning_service` de classification.

### ⚠️ Point de clarification important

**Le paragraphe descriptif que tu as rédigé correspond à l'architecture v1 (réutilisation de `extracted_text`), alors que le code que tu m'as fourni implémente déjà l'architecture v2 (extraction indépendante).** Les deux ne racontent pas la même chose : soit le paragraphe doit être mis à jour pour refléter le code actuel, soit c'est volontaire (documentation de l'ancienne version à des fins de comparaison). Dans un rapport de projet (PFE, soutenance…), je recommande d'aligner le texte narratif sur le code réellement en production pour éviter toute confusion.

**Pourquoi ce changement d'architecture a du sens** :
- La classification cherche un signal *rapide* (quelques mots-clés suffisent à typer un document) ; le RAG a besoin d'un texte *complet et fidèle*, y compris pour des tableaux, ce que l'OCR de classification n'est pas forcément optimisé pour produire.
- Découpler les deux pipelines évite qu'une modification du moteur RAG (chunking, OCR page complète, détection de sous-documents) n'impacte les performances ou la fiabilité de la classification, déjà en production.
- L'exécution en **thread asynchrone séparé** avec sa **propre session SQLAlchemy** (`rag_trigger.py`) confirme cette volonté d'isolation totale entre les deux flux.

---

## 4. Vue d'ensemble du flux d'exécution

1. Un document est classifié (`Qwen`) comme `CPS`, `RC` ou `BDP`.
2. `rag_trigger.lancer_rag_tender_async(tender_id)` est appelé → lance un thread daemon dédié.
3. Dans ce thread, une requête SQL sélectionne tous les documents du tender déjà classifiés **et** dont `file_type` est `CPS`, `RC` ou `BDP`.
4. Pour chaque document, `rag_pipeline_service.execute_rag_pipeline()` est exécuté (via `asyncio.run`, séquentiellement).
5. `traiter_extraction_rag()` ré-extrait le texte intégral du fichier source (PDF natif, OCR page-par-page si scanné, DOCX, Excel…).
6. Les pages/feuilles correspondant à des **modèles internes** (CV, Déclaration sur l'honneur, Acte d'Engagement…) sont détectées et extraites en PDF séparés dans `rag_extracted/`.
7. Le texte est enrichi par **GLM-OCR** (nettoyage, structuration des tableaux).
8. Le texte enrichi est découpé en chunks (`DocumentChunker`).
9. Les chunks sont vectorisés (`BGE-M3` via Ollama) et indexés dans **ChromaDB**, dans une collection unique par tender.
10. Une requête sémantique fixe interroge l'ensemble de la collection du tender (top-k = 6).
11. Le contexte récupéré est transmis à **Granite 4.1:3B**, qui produit un JSON structuré (`rag_analysis`).
12. Le résultat, le statut et les métriques (durées, nombre de chunks…) sont persistés dans `RAGAnalysisResult`.

---

## 5. Détail des composants

### 5.1 `rag_trigger.py` — Déclenchement asynchrone

Rôle : lancer le pipeline RAG **sans bloquer** le flux de classification, avec une isolation stricte des ressources.

Points clés :
- `threading.Thread(daemon=True)` : le thread ne bloque pas l'arrêt de l'application.
- Une **nouvelle session `SessionLocal()`** est ouverte dans le thread — la session utilisée par la classification n'est jamais partagée (évite les conflits de concurrence SQLAlchemy).
- Filtrage explicite : seuls les documents `is_classified == True` et `file_type in ["CPS", "RC", "BDP"]` déclenchent une analyse RAG. Les avis, BPU seuls, etc. ne sont pas traités ici.
- Chaque document est traité **séquentiellement** dans une boucle `for`, avec gestion d'erreur individuelle (`try/except` par document) pour qu'un échec sur un document n'interrompe pas les autres.

### 5.2 `rag_document_extractor.py` — Extraction indépendante & détection de documents internes

C'est le cœur de la nouveauté architecturale. Trois responsabilités distinctes :

**a) Extraction multi-format**
| Format | Méthode |
|---|---|
| PDF (texte natif) | `page.get_text("text", sort=True)` via PyMuPDF |
| PDF scanné | Fallback OCR page complète via RapidOCR (`extraire_page_complete_fast_ocr`) |
| DOCX | `python-docx`, paragraphes + tableaux linéarisés (`|` comme séparateur) |
| DOC | Conversion préalable en PDF via LibreOffice headless, puis traitement PDF |
| XLS/XLSX/XLSM | `pandas.read_excel`, toutes les feuilles, lignes vides ignorées |
| Images (PNG/JPG/TIFF…) | OCR direct RapidOCR |

La détection « page scannée » repose sur une heuristique `_ocr_est_de_mauvaise_qualite()` : texte trop court (< 250 caractères), ratio de lettres trop faible, ou trop de caractères « parasites » (`+*#=<>\|~`). C'est un choix pragmatique raisonnable, mais purement empirique — à surveiller sur des documents avec beaucoup de tableaux (ratio de lettres naturellement bas).

**b) Détection de documents internes**

Le dictionnaire `DOCUMENT_PATTERNS` associe à chaque type de document (`CPS`, `RC`, `BDP`, `BPU`, `DPGF`, `ACTE_ENGAGEMENT`, `DECLARATION_HONNEUR`, `DECLARATION_IDENTITE`, `CURRICULUM_VITAE`, `DECLARATION_FISCALE`, `DECLARATION_SOCIALE`) une liste de regex appliquées sur le texte normalisé (minuscule, apostrophes normalisées, espaces compactés).

`extraire_pages_modeles_pdf()` applique cette détection **page par page** dans un PDF (souvent un CPS ou un RC volumineux qui contient, en annexe, des modèles vierges de CV, déclaration sur l'honneur, etc.), avec une marge de contexte (`contexte_pages=1`) pour ne pas couper un modèle à cheval sur deux pages. Chaque type détecté donne lieu à un mini-PDF reconstruit (`fitz.open()` + `insert_pdf`).

C'est ce mécanisme qui explique la présence, dans `rag_extracted/.../AO-123_.../`, de sous-dossiers `CV/`, `DECLARATION_HONNEUR/`, `ACTE_ENGAGEMENT/`, etc. **à côté** du dossier `CPS/` ou `RC/` d'origine : un même fichier source peut « essaimer » plusieurs documents modèles.

**c) Orchestration de l'extraction — `traiter_extraction_rag()`**

Construit l'arborescence de sortie (`rag_extracted/AAAA/MM/JJ/<référence_nettoyée>/`), appelle l'extraction générique, puis :
- si PDF → extrait les pages-modèles et les range dans leur sous-dossier respectif ;
- si Excel → si un feuille est détectée comme `BDP`/`BPU`/`DPGF`, la convertit en PDF via ReportLab (`extraire_bdp_excel_vers_pdf`) pour la rendre exploitable par le workflow de génération de documents.

> **Note de cohérence avec le schéma** : dans ton diagramme modifié, la « Détection des documents internes » est représentée comme une étape générique après le branchement par format (PDF / DOC / XLS / XML). Dans le code actuel, cette détection-extraction **fine, page par page, avec génération de sous-PDF** n'est réellement implémentée que pour les branches **PDF** et **Excel** (`.xls/.xlsx/.xlsm`). Les DOCX/DOC bénéficient de l'extraction de texte complète, mais pas encore de la découpe en sous-documents modèles. Ce n'est pas forcément un problème (les DOCX combinés multi-modèles sont probablement rares côté marchés publics), mais c'est une différence entre le schéma cible et l'implémentation actuelle à garder en tête.
>
> Autre point : le format **`.xml`** apparaît dans le schéma (« XML → conservation + lecture ») mais n'est pas géré dans `extraire_document_complet_pour_rag()` — l'extension tomberait actuellement dans la branche « extension non supportée ». À ajouter si des fichiers XML sont réellement attendus dans les archives.

### 5.3 `rag_service.py` — Orchestrateur du pipeline (`RAGPipelineService`)

Point d'entrée unique : `execute_rag_pipeline(db, document_id)`, exécuté une fois par document éligible.

Déroulé réel (dans l'ordre du code) :

1. Récupération du `TenderDocument` et de/création du `RAGAnalysisResult` associé (relation 1-to-1), statut mis à `"IN_PROGRESS"`.
2. Construction du chemin de sortie `rag_extracted/AAAA/MM/JJ/<référence>` à partir de `tender.extraction_date` et `tender.reference` (nettoyée des caractères interdits pour un nom de dossier).
3. Appel à `traiter_extraction_rag()` → texte brut réel du document (indépendant de `extracted_text`).
4. Enrichissement via `_call_glm_ocr()` (voir 5.7) — le texte enrichi remplace le texte brut en cas de succès, sinon fallback silencieux sur le texte brut.
5. **Persistance intermédiaire** : `rag_entry.extracted_text = enhanced_text` — un commit dédié avant de continuer, pour ne jamais perdre le texte extrait même si la suite du pipeline échoue.
6. Chunking (`DocumentChunker.create_chunks`).
7. Génération des embeddings (`embedding_service.generate_embeddings`).
8. Indexation ChromaDB avec des métadonnées riches par chunk (`tender_reference`, `document_id`, `file_name`, `doc_type`, `chunk_index`).
9. Recherche sémantique **sur l'ensemble de la collection du tender** (pas filtrée par document), avec une requête fixe orientée métier (« Objet, dates importantes, pièces administratives et techniques, clauses, critères d'évaluation et pénalités »).
10. Appel à Granite 4.1:3B avec le contexte récupéré + `doc.file_type` comme information de type.
11. Sauvegarde finale : statut `COMPLETED`, `rag_analysis` (JSON brut), nom de collection Chroma, nombre de chunks, durées (embedding, extraction, LLM, total).
12. En cas d'exception à n'importe quelle étape : statut `FAILED` + `error_message`.

> **Point d'attention métier** : au step 9, `query_tender_context()` est appelée **sans** le paramètre `document_id`, alors que la méthode le supporte. Cela signifie que pour un tender ayant CPS + RC + BDP déjà indexés, **chaque document interroge le même contexte global** (tout le dossier), avec la **même requête générique**. Résultat probable : les trois `RAGAnalysisResult` (un par document) convergent vers un JSON très similaire, alors que `doc.file_type` est passé à Granite comme si l'analyse était spécifique au document. Deux pistes selon l'intention voulue :
> - si l'objectif est une **analyse consolidée par tender** → il serait plus cohérent de ne générer qu'un seul `rag_analysis` au niveau du tender (et non un par document) ;
> - si l'objectif est une **analyse spécifique par document** → il faudrait passer `document_id=str(doc.id)` à `query_tender_context()` pour restreindre la recherche aux chunks du document courant.

### 5.4 `chunker.py` — `DocumentChunker`

Découpage **par mots** (`text.split()`), pas par caractères — ce choix est justifié explicitement dans le docstring pour la compatibilité FR/AR (le split sur les espaces reste valide quel que soit le script, contrairement à un découpage par caractères qui poserait des soucis avec la segmentation arabe).

- `chunk_size=800` mots, `overlap=150` mots (configuré dans `RAGPipelineService.__init__`).
- Fenêtre glissante (`step = chunk_size - overlap`), chaque chunk garde son `chunk_id`, `word_count`, et un `page_number` optionnel (non renseigné actuellement, car le texte enrichi par GLM-OCR n'est plus segmenté par page à ce stade).
- Validation explicite `overlap < chunk_size` à l'instanciation.

C'est une implémentation simple, robuste et sans dépendance lourde (pas de tokenizer externe) — cohérent avec la contrainte CPU-only du projet.

### 5.5 `embeddings.py` — `OllamaEmbeddingService`

Appel HTTP vers `Ollama /api/embed` avec le modèle configuré (`settings.MODEL_EMBEDDINGS`, censé être `BAAI/bge-m3`). Le paramètre `keep_alive` permet de libérer immédiatement la RAM après usage (`OLLAMA_KEEP_ALIVE=0`), un choix cohérent avec une contrainte machine limitée (mentionné en commentaire : optimisation pour 16 Go de RAM).

Gestion d'erreur minimale : en cas de code HTTP ≠ 200, retourne une liste vide plutôt que de lever une exception — à surveiller, car cela peut faire échouer silencieusement le chunking en aval (`generate_embeddings` renverrait `[]`, ce qui ferait planter `collection.upsert()` avec une liste vide d'embeddings alors que les chunks existent).

### 5.6 `vector_store.py` — `ChromaDBManager`

Choix structurant : **une collection ChromaDB par appel d'offres** (`tender_<référence_nettoyée>`), et non une collection par document. Cela permet :
- une recherche sémantique unifiée sur tout le dossier (CPS + RC + BDP ensemble) ;
- une gestion de cycle de vie simple : `delete_document_chunks()` peut retirer uniquement les chunks d'un document (via un filtre `where={"document_id": ...}`) sans toucher au reste du tender, utile en cas de re-scan.

`store_document_chunks()` utilise `upsert()` avec des IDs déterministes (`doc_{document_id}_chunk_{i}`), ce qui rend l'opération idempotente : relancer le pipeline sur le même document remplace proprement ses anciens chunks plutôt que de les dupliquer.

`PersistentClient` avec `anonymized_telemetry=False` — bon réflexe pour un déploiement local/on-premise.

### 5.7 `prompts.py` — Prompts métier

**`GLM_OCR_PROMPT`** : prompt de reformattage/nettoyage (préserver montants, dates, références, structure des tableaux, gérer FR/AR, ne jamais halluciner). Utilisé comme étape de « mise en forme » avant l'extraction métier.

> **Point d'attention** : dans `_call_glm_ocr()`, malgré le nom « Vision Language Model » et l'objectif affiché de « compréhension visuelle », l'appel actuel à Ollama n'envoie **que du texte** (`raw_text`) — le bloc de code qui encoderait l'image de la page en base64 et l'ajouterait au payload (`payload["images"] = [...]`) est **commenté**. GLM-OCR fonctionne donc aujourd'hui comme un **reformateur de texte**, pas comme un véritable VLM exploitant le rendu visuel des pages. Ce n'est pas forcément un problème à court terme (le texte vient déjà d'un OCR + PyMuPDF de qualité), mais la promesse du schéma (« Compréhension visuelle », « Structure des tableaux » à partir de l'image) n'est pas encore pleinement réalisée techniquement — à clarifier si c'est un chantier en cours ou un choix définitif.
>
> Détail mineur : `raw_text` est injecté deux fois dans le prompt final (une fois via `{GLM_OCR_PROMPT}\n\nContenu initial :\n{raw_text}`, puis une seconde fois concaténé dans le payload `f"{prompt}\n\nContenu initial / brut:\n{raw_text}"`). Redondant, sans impact fonctionnel majeur, mais consomme inutilement du contexte token.

**`GRANITE_EXTRACTION_PROMPT`** : prompt d'extraction métier structurée avec règles anti-hallucination explicites (« ne jamais inventer », « utiliser `null` si absent », distinction estimation financière / caution provisoire, délai d'exécution / délai de validité). Bonne pratique pour un cas d'usage juridique/administratif où la précision prime sur l'exhaustivité créative.

### 5.8 `schemas.py` & `models.py` — Structuration et persistance

`TenderRAGAnalysisResult` (Pydantic) définit la forme attendue du JSON métier (`ImportantDates`, `RequiredDocuments`, listes de clauses, critères, pénalités…).

> **Incohérence de nommage repérée** : le prompt `GRANITE_EXTRACTION_PROMPT` demande la clé JSON `"maitre_d_ouvrage"`, alors que le schéma Pydantic définit le champ `maitre_douvrage` (sans les underscores internes). Si ce schéma est un jour utilisé pour valider/parser la sortie de Granite (actuellement `rag_service.py` importe `TenderRAGAnalysisResult` mais ne l'utilise nulle part — le JSON est stocké brut, sans validation), cette divergence ferait échouer le mapping automatique. À aligner dans un sens ou dans l'autre.

Côté SQLAlchemy (`models.py`), `RAGAnalysisResult` porte le statut (`RAGStatus` enum : `PENDING`, `INDEXING`, `ANALYZING`, `COMPLETED`, `FAILED`), le texte enrichi, le JSON brut (`JSONB`), et un ensemble de métriques de traçabilité (durées, nombre de chunks, modèles utilisés).

> **Deux incohérences techniques à corriger** :
> 1. Dans `rag_service.py`, le statut `"IN_PROGRESS"` est assigné à `rag_entry.status`, mais cette valeur **n'existe pas** dans l'enum `RAGStatus` (qui contient `PENDING/INDEXING/ANALYZING/COMPLETED/FAILED`). Selon la configuration de la colonne (`Enum(RAGStatus)`), cela peut lever une erreur d'intégrité à l'écriture, ou être silencieusement toléré selon le driver — à corriger en utilisant `RAGStatus.INDEXING` ou `RAGStatus.ANALYZING`, ou en ajoutant `IN_PROGRESS` à l'enum.
> 2. Le champ `error_message` est déclaré **deux fois** dans la classe `RAGAnalysisResult` (une fois avant les champs de traçabilité de modèle, une fois juste après `llm_extraction_duration_sec`). La seconde déclaration écrase silencieusement la première au niveau du mapper SQLAlchemy — sans effet fonctionnel visible immédiatement, mais à nettoyer pour la lisibilité et éviter des surprises lors d'une migration Alembic.

Par ailleurs, `BASE_STORAGE_DIR` est défini dans `rag_service.py` comme une **chaîne brute** (`r"C:\Users\...\data_storage"`) alors qu'il est ensuite utilisé avec l'opérateur `/` propre aux objets `pathlib.Path` (`Path(extracted_root) / "rag_extracted"` — non, en l'occurrence c'est `str(BASE_STORAGE_DIR / "rag_extracted")` directement). Une chaîne Python ne supporte pas l'opérateur `/` : cette ligne lèverait un `TypeError` à l'exécution telle quelle. Il faut soit envelopper `BASE_STORAGE_DIR` dans `Path(...)` à la définition, soit utiliser `os.path.join`. À vérifier — c'est probablement un chemin encore en dur pour le développement local (Windows), à remplacer par `settings.CHROMA_PERSIST_DIR.parent` ou une variable d'environnement dédiée avant la mise en production (cohérent avec le reste de `config.py`, qui centralise déjà tout via `.env`).

---

## 6. Organisation du stockage disque

```
data_storage/
├── classified/…/TYPE/fichier.pdf        ← sortie de la classification (Qwen)
├── extracted/…/ao_xx/*.pdf              ← pièces décompressées brutes de l'archive scrapée
├── rag_extracted/AAAA/MM/JJ/<réf_AO>/   ← sortie DÉDIÉE du pipeline RAG
│   ├── CPS/
│   ├── RC/
│   ├── BDP/
│   ├── CV/
│   ├── DECLARATION_HONNEUR/
│   ├── ACTE_ENGAGEMENT/
│   └── DECLARATION_IDENTITE/
└── chroma_db/                            ← index vectoriel persistant (SQLite + HNSW)
```

Ce cloisonnement est une bonne pratique : `extracted/` (classification) et `rag_extracted/` (RAG) ne se marchent jamais dessus, même s'ils traitent en partie les mêmes fichiers sources. Cela confirme au niveau du système de fichiers l'indépendance déjà actée au niveau du code.

---

## 7. Points forts de l'architecture

- **Isolation totale** entre classification et RAG (thread séparé, session DB séparée, dossier de sortie séparé) — limite le risque de régression sur la classification déjà en production.
- **Choix CPU-only cohérent** : RapidOCR ONNX, BGE-M3 et Granite 4.1:3B via Ollama en local, avec gestion active de la RAM (`keep_alive`), pas de dépendance GPU.
- **Multilinguisme FR/AR pris au sérieux** à plusieurs niveaux : choix de BGE-M3 (embeddings multilingues), chunking par mots (agnostique au script), prompts qui rappellent explicitement de respecter le français et l'arabe.
- **Détection de sous-documents modèles** (CV, déclarations, actes) directement dans les PDF combinés — évite d'avoir à retraiter manuellement des dossiers scannés massifs.
- **Idempotence de l'indexation** (upsert avec IDs déterministes) : relancer le pipeline sur un document ne duplique pas les données.
- **Anti-hallucination explicite** dans les prompts métier (`null` si absent, ne jamais inventer) — adapté au contexte juridique/administratif des marchés publics.
- **Traçabilité fine** : chaque `RAGAnalysisResult` conserve les durées par étape, le nombre de chunks, le nom de la collection Chroma — bonne base pour un futur tableau de bord de performance (`telemetry/`).

---

## 8. Synthèse des points de vigilance techniques

| # | Fichier | Problème | Impact |
|---|---|---|---|
| 1 | `rag_service.py` | `BASE_STORAGE_DIR` est une `str`, utilisée avec l'opérateur `/` propre à `Path` | Erreur d'exécution probable (`TypeError`) |
| 2 | `rag_service.py` | Statut `"IN_PROGRESS"` absent de l'enum `RAGStatus` | Risque d'erreur d'intégrité ou de valeur non contrôlée en base |
| 3 | `models.py` | `error_message` déclaré deux fois dans `RAGAnalysisResult` | Écrasement silencieux, dette technique |
| 4 | `schemas.py` / `prompts.py` | `maitre_douvrage` (schéma) vs `maitre_d_ouvrage` (prompt) | Mapping cassé si le schéma Pydantic est un jour utilisé pour valider la sortie |
| 5 | `rag_service.py` | Recherche sémantique non filtrée par `document_id` malgré le support existant | Résultats potentiellement redondants entre CPS/RC/BDP d'un même tender |
| 6 | `rag_service.py` (`_call_glm_ocr`) | Encodage image commenté : GLM-OCR n'analyse que du texte, pas l'image des pages | Écart entre la promesse « compréhension visuelle » et l'implémentation actuelle |
| 7 | `rag_document_extractor.py` | Pas de gestion du format `.xml` malgré sa présence dans le schéma cible | Fichiers XML non traités (branche « extension non supportée ») |
| 8 | `embeddings.py` | Retour `[]` silencieux si l'appel Ollama échoue | Risque de plantage en aval sur `collection.upsert()` avec des listes vides |

---

## 9. Pistes d'amélioration (optionnelles)

- **Clarifier la granularité de l'analyse** : une analyse RAG unique par tender (consolidée CPS+RC+BDP) plutôt qu'une par document, si l'objectif final est un dossier de synthèse unique — évite la redondance actuelle.
- **Ajouter un mécanisme de retry/backoff** sur les appels HTTP à Ollama (GLM-OCR, Granite, embeddings), pour absorber les cas de modèle en cours de chargement ou de RAM saturée.
- **Étendre `extraire_pages_modeles_pdf`-like logic aux DOCX** si des dossiers Word combinés multi-modèles existent en pratique.
- **Documenter formellement** si GLM-OCR restera un simple reformateur de texte, ou si le passage à un usage réellement visuel (image + prompt) est prévu à court terme — cela conditionne la valeur ajoutée réelle de cette étape par rapport à un passage direct du texte OCR à Granite.
- **Ajouter une validation Pydantic** de la sortie JSON de Granite (via `TenderRAGAnalysisResult`, une fois les clés alignées) avant persistance, pour détecter les dérives de format du LLM.

---

## 10. Conclusion

Le pipeline RAG de Waraq introduit une **couche d'analyse métier indépendante** de la classification, avec une architecture bien pensée pour un contexte CPU-only et multilingue FR/AR : extraction dédiée, détection fine de sous-documents, indexation vectorielle par tender, et extraction JSON anti-hallucination via Granite. Le découplage vis-à-vis de la classification (thread asynchrone, session DB séparée, dossier de sortie dédié) est le choix architectural le plus structurant et le plus solide du design actuel.

Les points de vigilance identifiés (bug `Path`/`str`, enum de statut incomplet, granularité de la recherche sémantique, portée réelle de GLM-OCR) sont typiquement le genre d'ajustements attendus à ce stade d'un module encore récent — aucun ne remet en cause la conception d'ensemble, mais leur correction avant la mise en production évitera des comportements silencieusement incorrects (notamment le point n°5, qui affecte directement la qualité perçue des résultats métier).
