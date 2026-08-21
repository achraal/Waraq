Cahier des Charges : Projet Waraq (ex-

MarocAO) 

*Un écosystème intelligent pour l'automatisation, la classification et le traitement des appels d'offres publics au Maroc* 

1. Description du Projet** 

**Waraq** (ex-MarocAO) est une plateforme SaaS d'**Intelligent Document Processing (IDP)** et d'automatisation métier conçue pour simplifier, accélérer et sécuriser l'analyse ainsi que la réponse aux marchés publics marocains.  

Le système s'interconnecte au portail officiel des marchés publics (et suit les flux d'alertes emails PMMP) pour collecter automatiquement les avis, les métadonnées et les Dossiers de Consultation des Entreprises (DCE). Grâce à une architecture IA hybride hébergée en local (combinaison de règles primitives, moteurs OCR multi-formats et LLM local **Qwen 2.5:7b**), Waraq assure la classification multi-documents, le découpage intelligent des pièces imbriquées et la possibilité pour l'utilisateur de valider/corriger en temps réel le traitement (*Human-in-the-Loop*).  

En phase aval, la plateforme fusionne les métriques extraites du marché avec le profil juridique de l'entreprise connectée pour générer instantanément les documents officiels de candidature (.docx).  

2. Objectifs du Projet 
- **Économique & Gain de Temps :** Réduire de plus de 90 % le temps de préparation administratif nécessaire pour postuler à un marché public au Maroc.** 
- **Classification & Découpage Précis :** Traiter tous les formats d'un DCE (.pdf, .docx, .xlsx, images scannées, .dwg/.dxf, .doc) sans blocage tout en isolant automatiquement les pièces internes imbriquées. , .doc) sans blocage tout en isolant automatiquement les pièces internes imbriquées.**  
- **Souveraineté & Traitement IA Local :** Utiliser exclusivement un modèle d'IA open-source hébergé en local (**Qwen 2.5:7b via Ollama**) pour garantir le secret professionnel et la confidentialité stricte des données d'affaires. **Qwen 2.5:7b via Ollama**) pour garantir le secret professionnel et la confidentialité stricte des données d'affaires.**  
- **Contrôle Qualité & Apprentissage Continu :** Offrir une boucle *Human-in-the-Loop* avec *Dynamic Few-Shot Prompting* pour permettre aux administrateurs de réajuster les classifications et réentraîner le modèle localement.** 
- **Télémétrie & Traçabilité :** Garantir un suivi temps réel de la santé de l'infrastructure (CPU, BDD, Taux de réussite IA) et garder un registre d'audit clair de chaque action de classification. Garantir un suivi temps réel de la santé de l'infrastructure (CPU, BDD, Taux de réussite IA) et garder un registre d'audit clair de chaque action de classification.** 
- **Sécurité Absolue :** Protéger l'accès aux identifiants sensibles des entreprises candidates via un chiffrement et un hachage cryptographique de pointe. 
3. Acteurs du Système 
- **L'Entreprise Candidate (Soumissionnaire) :** Configure son profil selon sa nature juridique, recherche et suit les opportunités, consulte les résumés d'IA et télécharge ses pièces administratives générées automatiquement.** 
- **L'Administrateur (Sigma Power / Start-up) :** Supervise l'intégrité des scripts de scraping, surveille la charge du LLM local, configure les invites (prompts) système et analyse l'activité globale du produit.** 
- **Le Visiteur :** Accède à la vitrine marketing et à un mode de démonstration restreint. 
4. Besoins Fonctionnels 

Module 1: Web Scraping, Monitoring & Ingestion (Amont) 

- **Parsing Structuré :** Extraction rapide via BeautifulSoup des métadonnées visibles (Réf, Objet, Acheteur, Date limite) pour peupler immédiatement la base de données.** 
- **Collecte Automatisée Multi-Lots :** Navigation autonome sur le portail d'État, extraction des marchés simples et multi-lots (TenderLot), et téléchargement des archives brutes .zip. .zip.**  
- **Extraction Récursive des Archives :** Gestion automatique du stockage physique dans /archives et décompression récursive des sous-dossiers ZIP ou documents imbriqués. /archives et décompression récursive des sous-dossiers ZIP ou documents imbriqués.**  
- **Monitoring Emails (PMMP) :** Surveillance de la boîte Gmail configurée pour lire, parser et remonter les notifications de nouveaux marchés publics en temps réel.** 
- **Exports Structurés :** Génération de rapports Excel stylisés reprenant les métadonnées globales des offres et de leurs lots associés.**Exports Structurés :** Génération de rapports Excel stylisés reprenant les métadonnées globales des offres et de leurs lots associés. 

  Module 2 : Authentification & Profiling Juridique Multi- Structures** 

- **Sécurisation des Accès :** Hachage robuste Argon2id, gestion du cycle de vie des jetons JWT et contrôle d'accès basé sur les rôles (Admin vs Candidat). **Sécurisation des Accès :** Hachage robuste Argon2id, gestion du cycle de vie des jetons JWT et contrôle d'accès basé sur les rôles (Admin vs Candidat).**  
- **Gestion des 5 Typologies Juridiques :** L'architecture repose sur un modèle d'héritage polymorphe (**CompanyProfile) subdivisé en Personnes Physiques (PhysicalPersonProfile) et Personnes Morales (LegalPersonProfile), couvrant l'intégralité des champs obligatoires pour les actes de candidature (Acte d'Engagement & Déclaration sur l'Honneur) :** 
1. **Personne Physique (INDIVIDUAL\_PROPER) :*** 
- *Type d'héritage :* PhysicalPersonProfile* 
- *Champs spécifiques :* Manager (Nom, prénom et qualité), Adresse (Domicile élu), CIN, Patente / Taxe Professionnelle, RIB (24 positions), Banque, RC (Registre du Commerce) et Localité (optionnels).** 
2. **Auto-Entrepreneur (AUTO\_ENTREPRENEUR) :*** 
- *Type d'héritage :* PhysicalPersonProfile* 
- *Champs spécifiques :* Manager, Adresse, CIN, Numéro de Carte d'Auto- Entrepreneur, Patente / Taxe Professionnelle, RIB, Banque. *(ICE et RC non requis)*.** 
3. **Société / Personne Morale (COMPANY) :*** 
- *Type d'héritage :* LegalPersonProfile* 
- *Champs spécifiques :* Raison sociale (company\_name), Capital social, RC obligatoire & Localité, Patente / Taxe Professionnelle, RIB, Banque, Affiliation CNSS (optionnelle), ICE (optionnel/unique).** 
4. **Établissement / Institution Public (PUBLIC\_INSTITUTION) :*** 
- *Type d'héritage :* LegalPersonProfile* 
- *Champs spécifiques :* Nom de l'établissement (company\_name), Texte d'habilitation légale ou Décret d'autorisation (legal\_authorization\_text), RC & Localité, Patente / Taxe Pro, RIB, Banque.** 
5. **Coopérative (COOPERATIVE) :*** 
- *Type d'héritage :* LegalPersonProfile* 
- *Champs spécifiques :* Raison sociale (company\_name), Numéro du Registre des Coopératives (cooperative\_register\_number), Capital social, RC & Localité, Patente / Taxe Pro, RIB, Banque. 

Module 3: Intelligent Document Processing (IDP) & IA Hybride 

- **Moteur d'OCR & Extraction de Texte :** Lecture et traitement du texte brut contenu au sein des PDF (Avis, RC, CPS).** 
- **Analyse Contextuelle LLM :** Extraction automatique par une IA locale des données financières et temporelles clés (Montant de la caution provisoire, estimation financière globale TTC, délai de validité des offres, monnaie, langues admises).** 
- **Moteur d'Extraction OCR Multi-formats :** 
- Traitement des PDF natifs via extraction structurée. 
- Traitement des documents scannés / images via **Tesseract / PaddleOCR**. 
- Optimisation automatique préalable des images géantes via Pillow (max\_side=2048) pour éviter la saturation mémoire. 
- Conversion dynamique des fichiers .doc legacy via LibreOffice headless. 
- Extraction directe du texte pour les fichiers Office (.docx, .xlsx) et typage dédié pour la CAO (.dwg, .dxf).** 
- Bypass instantané (0.00s) pour les métadonnées géographiques SIG (.jgw, .tfw).* 
- **Classification Hybride à 2 Niveaux :*** 
- *Niveau 1 (Primitives / Règles métier) :* Identification ultra-rapide des types connus (CPS, RC, BDP, Avis, CCATP, CCFTP, etc.).* 
- *Niveau 2 (Fallback LLM Qwen 2.5:7b) :* Analyse sémantique par l'IA locale si le document dépasse le cadre des primitives.** 
- **Découpage Intelligent des Pièces Imbriquées :** Scan page par page des PDF volumineux pour extraire et classer séparément les pièces cachées (ex : un BDP enfoui dans un CPS).** 
- **Module Human-in-the-Loop (/validate) :** Interface d'inspection et de correction proposant 4 workflows :* 
1. *Validation simple :* Confirmation de la décision de l'IA.* 
1. *Correction simple :* Re-typification manuelle sans redécoupage.* 
1. *Undo Split :* Annulation d'un découpage abusif fait par l'IA et restauration du document parent.* 
1. *Redécoupage Manuel :* Définition manuelle des plages de pages (*start\_page* $\rightarrow$ *end\_page*) pour ré-ajuster la segmentation.** 
- **Apprentissage Continu (Learning Loop) :** 
- Injection dynamique des corrections humaines dans le prompt (*Dynamic Few-Shot Prompting*). 
- Endpoints d'export de dataset au format JSONL et déclenchement d'entraînement local (*train-local*). 
- **Pipeline RAG en Parallèle (Retrieval-Augmented Generation)** :  
- **Déclenchement automatique** : Dès la fin de la classification automatique (Qwen 2.5:7b), le pipeline RAG se lance sans altérer le flux de classification.  
- **Réutilisation OCR** : Exploitation directe du texte déjà extrait par RapidOCR ONNX et stocké dans le champ extracted\_text, évitant toute ré-exécution d'OCR.  
- **Chunking & Embeddings** : Découpage du texte en segments (chunks) et vectorisation à l'aide du modèle multilingue **BAAI BGE-M3** (optimisé pour le français et l'arabe).  
- **Indexation Vectorielle** : Stockage et gestion des représentations vectorielles dans la base de données **ChromaDB**.  
- **Recherche Sémantique & Extraction LLM** : Récupération ciblée des passages pertinents selon le type de document identifié et transmission au modèle **Granite 4.1:3B** pour l'extraction métier.  
- **Isolation & Persistence des Données** : Enregistrement du résultat de l'analyse dans un champ JSON dédié (ex: rag\_analysis), distinct du champ extracted\_text d'origine pour préserver l'intégrité de la donnée source.  
- **Analyse Métier Structurée Générée par RAG** :  
- Extraction automatique des informations clés du marché : objet de l'appel d'offres, maître d'ouvrage, références, dates importantes, pièces administratives et techniques à fournir, 

  clauses administratives/techniques, critères d'évaluation, garanties, délais d'exécution et pénalités.  

- Alimentation directe des modules aval : génération de résumés, synthèses, checklists de conformité du dossier de candidature et assistance automatique à la préparation des réponses. 

Module 4 : Génération Automatique de Documents de Réponse (Workflows) 

- **Extraction & Remplissage des Modèles de BDP (Bordereau des Prix)** : 
- Extraction automatique de la structure du Bordereau des Prix à partir du document source.  
- Remplissage dynamique des prix unitaires/totaux et génération du fichier BDP final complété.  
- **Gestion Dynamique des Modèles Administratifs** : 
- Extraction et complétion automatique des modèles fournis dans le DCE (Acte d'engagement, Déclaration sur l'honneur, Déclaration d'identité, CVs, etc.).  
- **Fallback / Modèles par Défaut** : Si aucun modèle n'est fourni dans le DCE, le système injecte et remplit automatiquement les modèles officiels standards de Waraq (Acte d'engagement et Déclaration sur l'honneur) pré-configurés selon le profil juridique du soumissionnaire.  
- **Moteur de Apposition de Signature & Paraphe Automatique** : 
- **Signature de toutes les pages** : Application automatique du tampon/signature électronique sur l'ensemble des pages du Cahier des Prescriptions Spéciales (CPS) et du Règlement de Consultation (RC).  
- **Détection des mentions obligatoires** : Identification automatique des zones de validation (ex: case *"Lu et accepté"*) et apposition de la mention accompagnée de la signature/tampon. 

Module 5: Télémétrie, Audit & Observabilité System 

- **Module Telemetry :** Capture périodique (cron horaire / déclenchement manuel) de l'état de santé globale : 
- Disponibilité et performances de la BDD PostgreSQL. 
- Métriques de classification IA (temps de réponse, taux de réussite). 
- Métriques du scraper et ressources serveur/hardware.** 
- **Audit de Classification (ClassificationAuditLog) :** Historisation et traçabilité détaillée de chaque document (statuts de validation, raisons de classification, modifications utilisateur, horodatage). 

  Module 6 : Interface Utilisateur & Tableau de Bord (React)** 

- **Dashboard des Marchés :** Vue moderne avec filtres avancés par budget, mots-clés, deadline, statut de consultation (is\_consulted) et catégories.**  
- **Espace Documentaire & Inspection Natif :** Visualisation des rapports de l'IA, prévisualisation directe des documents natifs (/view) et graphiques de répartition par motif de classification (/stats/classification-reasons).** 
- **Design & Typographie :** Interface stylisée sous Tailwind CSS intégrant la police *Geist*. 
5. Besoins Non Fonctionnels & Sécurité 

Performance & Scalabilité 

- **Primitives Ultra-Rapides :** Les classifications par règles métier/heuristiques (Level 1) doivent s'exécuter de manière quasi instantanée ($< 0.1\text{s}$ par document).** 
- **Gestion Avancée de la Mémoire (RAM/GPU) :** Traitement optimisé des fichiers haute définition (redimensionnement automatique des images à max $2048\text{px}$ via Pillow) afin de prévenir les erreurs de dépassement mémoire (*MemoryError* / *Out of Memory*).** 
- **Contrôle des Délais (Timeouts) :** Mise en place d'un mécanisme de tolérance aux pannes sur le LLM (**Qwen 2.5:7b**) pour capturer les ReadTimeout d'Ollama sans interrompre la file d'attente globale de classification.** 
- **Optimisation des Requêtes BDD :** Temps de réponse des requêtes de filtrage et d'agrégation (/stats/classification-reasons) sous les $200\text{ms}$ grâce à l'indexation PostgreSQL sur les clés étrangères et les champs de statut. 

  Sécurité & Confidentialité** 

- **Cryptographie des Accès :** Hachage renforcé des mots de passe avec l'algorithme **Argon2id** et gestion des sessions stateless via des jetons **JWT (JSON Web Tokens)** expirables. **JWT (JSON Web Tokens)** expirables.**  
- **Isolation & Souveraineté des Données :** Exécution 100 % locale du modèle de langage (**Qwen 2.5:7b** via Ollama) garantissant le secret professionnel et la protection des informations sensibles des soumissionnaires (pas de fuite de données vers des API Cloud tierces). **Qwen 2.5:7b** via Ollama) garantissant le secret professionnel et la protection des informations sensibles des soumissionnaires (pas de fuite de données vers des API Cloud tierces).**  
- **Contrôle d'Accès Basé sur les Rôles (RBAC) :** Séparation stricte des privilèges entre les utilisateurs candidats (accès restreint à leurs profils et dossiers) et les administrateurs (accès à la télémétrie, au scraping, aux logs d'audit et à la validation globale).** 
- **Sécurisation des Chemins Système (Path Traversal Protection) :** Assainissement (*sanitization*) rigoureux des noms de dossiers physiques sous Windows/Linux pour bloquer les erreurs de syntaxe (WinError) ou l'injection de caractères spéciaux (ex: remplacement automatique du / présent dans les références d'AO par des séparateurs sûrs). 

  Intégrité & Traçabilité du Stockage** 

- **Immutabilité des Données Sources :** Sauvegarde absolue des archives brutes dans data\_storage/archives/ et extraites dans data\_storage/extracted/ via une stratégie de copie explicite (shutil.copy2) vers data\_storage/classified/ au lieu d'un déplacement destructeur.** 
- **Traçabilité Intégrale (Audit Trail) :** Enregistrement de chaque action de classification, modification ou validation humaine dans la table ClassificationAuditLog pour permettre l'imputabilité et l'analyse de l'évolution des performances IA.** 
- **Télémétrie en Temps Réel :** Collecte continue (scheduler cron hourly) de l'état de santé matérielle et logicielle (CPU, RAM, état de la BDD PostgreSQL, taux de réussite IA) accessible via des endpoints dédiés. 

  Portabilité & Maintien en Condition Opérationnelle (MCO)** 

- **Reproductibilité des Dépendances :** Usage exclusif du gestionnaire **uv** et verrouillage des versions (uv.lock) pour garantir des builds strictement identiques quel que soit l'environnement de déploiement. uv.lock) pour garantir des builds strictement identiques quel que soit l'environnement de déploiement.**  
- **Tolérance aux Formats Hétérogènes :** Prise en charge transparente de multiples formats d'entrée (.pdf, .docx, .xlsx, .doc, .jpg, .png, .dwg, .dxf, .jgw, .tfw) sans crash du pipeline d'ingestion.** 
- **Modularité du Code (SOLID) :** Architecture backend découplée sous FastAPI permettant l'isolation des responsabilités (scrapers, moteurs d'OCR, processeur LLM, télémétrie) pour simplifier les évolutions futures. 
6. Architecture Technique** 
- **Frontend :** React.js (Vite), Tailwind CSS, Lucide Icons, Police Geist. **Frontend :** React.js (Vite), Tailwind CSS, Lucide Icons, Police Geist.**  
- **Backend :** FastAPI (Python) sous architecture modulaire (auth, tenders, scraper, ai\_processor, telemetry, audit). **Backend :** FastAPI (Python) sous architecture modulaire (auth, tenders, scraper, ai\_processor, telemetry, audit).**  
- **Base de Données :** PostgreSQL (géré via SQLAlchemy ORM et migrations incrémentielles Alembic). **Base de Données :** PostgreSQL (géré via SQLAlchemy ORM et migrations incrémentielles Alembic).**  
- **LLMs & Modèles IA** : 
- **Classification** : Qwen 2.5:7b (Ollama).  
- **Embeddings** : BAAI BGE-M3 (Multilingue FR/AR).  
- **Analyse Métier RAG** : Granite 4.1:3B.  
- **Bases de Données** : 
- **Relational Database** : PostgreSQL (SQLAlchemy ORM, migrations Alembic).  
- **Vector Database** : ChromaDB (stockage et recherche sémantique des chunks).  
- **Moteurs OCR & Traitement Documentaire** : 
- **OCR** : RapidOCR ONNX, PyMuPDF, Tesseract, PaddleOCR.  
- **Vision-LLM & OCR Multimodal Advanced** : **GLM-4V / GLM OCR** (dédié à la numérisation intelligente des documents complexes, tableaux, formulaires et mises en page structurées). 
- **Génération & Manipulation de Documents** : python-docx, python-pptx, PyPDF2 / pypdf, openpyxl, LibreOffice 
- **Gestionnaire de dépendances :** uv.** 
7. Planning Prévisionnel 



|**Phase** |**Durée** |**Tâches Principales** |
| - | - | - |
|**1. Conception & Environnement** |2 semaines |Validation du CDC, réalisation des diagrammes UML (Classes, Cas d'utilisation), initialisation de l'écosystème avec uv, configuration de PostgreSQL et création de l'arborescence globale. |
|**2. Module 1 : Web Scraping** |3 semaines |Codage de la logique de navigation automatique (portal\_scraper.py via Selenium) et du parser de contenu avec BeautifulSoup. |
|**3. Module 2 & 3 : Sécurité & BDD** |1 semaine |Implémentation du système d'authentification (Argon2id et génération/vérification des tokens JWT), configuration des routes d'accès et mise en place des modèles ORM SQLAlchemy avec héritage des profils juridiques. |
|**4. Module 4 : Moteur d'IA (IDP)** |2 semaines |Développement de la brique d'extraction de texte (PyMuPDF) et conception des invites de guidage (prompt engineering) pour l'analyse contextuelle et la classification locale avec Ollama. |
|**5. Module 5 : Génération & Front** |1 semaine |Développement du script d'automatisation de fichiers Word (.docx) et liaison de l'interface utilisateur React aux endpoints de l'API FastAPI. |
|**6. Tests & Déploiement** |1 semaine |Tests d'intégration de bout en bout, correction des anomalies, écriture du rapport technique final de stage et préparation du support de soutenance. |

