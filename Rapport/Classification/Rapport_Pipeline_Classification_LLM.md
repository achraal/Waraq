::::::::: titlepage
:::: minipage
::: flushleft
![image](./emsi.png){height="1.2cm"}
:::
::::

:::: minipage
::: flushright
![image](./sigma logo.png){height="1.3cm"}
:::
::::

Système Automatisé de Traitement des Marchés Publics\

------------------------------------------------------------------------

\
**Stratégie d'Apprentissage et d'Optimisation du Pipeline de
Classification Documentaire**\

------------------------------------------------------------------------

::: tcolorbox
**Document :** Rapport Technique d'Architecture & d'IA
:::

::: center
**Réalisé par :** Achraf\
**2026-08-10**
:::

> **Résumé ---** Ce document présente la conception technique et la
> stratégie d'apprentissage du module de classification automatique de
> documents pour la plateforme **Waraq**. À travers une approche hybride
> en cascade combinant des règles déterministes, l'extraction de texte
> natif et l'inférence par un Modèle de Langage (*LLM Qwen 2.5*), le
> pipeline garantit un traitement hautement performant, évolutif et
> auto-apprenant via une technique de *Few-Shot Learning* dynamique en
> temps réel.
:::::::::

# Contexte et Objectifs du Module de Classification

Dans le cadre de la modernisation et de la dématérialisation du
traitement des marchés publics au Maroc, la plateforme **Waraq** est
amenée à traiter, analyser et structurer à grande échelle une grande
diversité de documents administratifs et techniques.

Les typologies documentaires couvertes incluent notamment :

- **Avis d'Appels d'Offres** (Avis de publication) ;

- **Cahiers des Prescriptions Spéciales (CPS)** ;

- **Règlements de Consultation (RC)** ;

- **Bordereaux des Prix - Détails Estimatifs (BPDE)** ;

- **Actes d'Engagement** et pièces administratives annexes.

L'objectif central de la stratégie mise en œuvre est d'assurer une
classification **rapide, ultra-précise et auto-apprenante**. Le système
exploite une synergie entre des règles déterministes à latence nulle,
une extraction directe de texte natif et une inférence IA basée sur un
Modèle de Langage (LLM), tout en intégrant une boucle de rétroaction
continue alimentée par les corrections des utilisateurs humains.

# Architecture Technique du Pipeline Hybride

Le pipeline de traitement s'articule autour d'une **approche en cascade
à quatre niveaux**, conçue pour optimiser l'utilisation des ressources
informatiques, réduire le temps d'inférence et maximiser la précision
globale.

## Représentation Schématique de la Cascade

::: center
:::

## Description Détaillée des Niveaux de Traitement

### Niveau 1 : Filtrage par Règles Primitives (Déterministe)

Avant de faire appel à des ressources informatiques lourdes
(GPU/CPU/OCR), le système applique un ensemble de règles déterministes
strictes basées sur les métadonnées primaires du fichier :

- Extensions spécifiques (ex. feuille de calcul `.xlsx`, `.csv` pour les
  bordereaux de prix).

- Préfixes ou motifs explicites dans le nom du fichier (ex. `CPS_*`,
  `RC_*`, `AVIS_*`).

Ce niveau permet de résoudre les cas évidents sans coût computationnel
ni latence.

### Niveau 2 : Extraction de Texte Natif

Afin d'éviter la lourdeur et les imprécisions d'un moteur d'OCR
(Reconnaissance Optique de Caractères sur image), le pipeline extrait
directement le texte natif encodé de l'ensemble du document PDF. Cette
méthode permet de capturer l'intégralité du contenu textuel du document
pour une analyse exhaustive.

### Niveau 3 : Classification par Inférence LLM (Qwen 2.5 : 7B)

Lorsque les règles primitives ne permettent pas de conclure, le texte
extrait est transmis au modèle de langage **Qwen 2.5 (7B)** via
l'environnement Ollama. Le modèle renvoie une structure JSON stricte
contenant :

- **Type de document :** Catégorie retenue (ex. `CPS`, `RC`, `Avis`).

- **Justification :** Explication en français motivant la décision.

- **Score de confiance :** Valeur normalisée entre 0.0 et 1.0.

- **Mots-clés prédominants :** Termes clés déterminants identifiés.

- **Langue :** Langue détectée du document (Français, Arabe).

### Niveau 4 : Analyse Poly-documentaire et Découpage Automatique

Pour les dossiers volumineux regroupant plusieurs sous-documents au sein
d'un même fichier PDF (ex. un dossier unique contenant l'Avis + le RC +
le CPS), le pipeline procède à une analyse structurelle par blocs de
pages, détecte les ruptures de contenu et effectue un découpage physique
automatisé.

# Stratégie d'Apprentissage Continu (*Few-Shot Learning* Dynamique)

Pour permettre à l'IA d'apprendre continuellement de ses erreurs sans
passer par des phases de réentraînement lourd **Fine-Tuning**, le
système exploite la technique d'**Apprentissage en Contexte (In-Context
Learning)**.

::: infoBox
Principe de Fonctionnement du Feedback Loop

1.  **Validation et Correction Humaine :** Lorsqu'un utilisateur corrige
    une classification sur la plateforme, le fichier passe au statut
    `CORRIGE` et conserve son type final validé.

2.  **Reconstruction du Contextualiseur :** À chaque nouvelle exécution,
    le moteur interroge la base de données PostgreSQL pour extraire les
    corrections historiques.

3.  **Extraction des Paires de Contexte :** Extraction des tuples :
    *(Extrait de texte d'origine $\rightarrow$ Correction validée)*.

4.  **Injection Dynamique (Prompt Engineering) :** Les erreurs passées
    sont intégrées sous forme d'exemples (*Few-Shot Examples*) dans la
    consigne système transmise à Qwen 2.5.
:::

## Avantages de l'Option A (Few-Shot vs Fine-Tuning)

  **Axe d'évaluation**           **Apport de l'In-Context Learning**
  ------------------------------ -------------------------------------------------------
  **Temps de Prise en Compte**   Instantané (dès le document suivant)
  **Adaptabilité Régionale**     Assimilation rapide du jargon administratif marocain
  **Sécurité du Modèle**         Préservation de l'intégrité des poids d'origine
  **Coût Computationnel**        Faible (pas de boucle de rétropropagation/GPU dédiée)

  : Comparatif des bénéfices de l'apprentissage en contexte.

# Déploiement Hybride et Déport des Calculs (Option B : Cloud / Colab)

Afin de préserver les ressources matérielles de l'environnement local
lors des phases intenses de **scraping** et d'entrées/sorties en base de
données, l'architecture permet de déporter la charge d'inférence LLM
vers une infrastructure distante accélérée par GPU (ex. Google Colab
avec NVIDIA T4).

## Architecture de Déport

- **Serveur Local Waraq :** Exécute les tâches d'acquisition
  (**scraping**), la gestion de la base PostgreSQL, l'extraction
  textuelle et l'organisation des fichiers.

- **Serveur Distant Dedié :** Héberge le moteur **Ollama** sur GPU et
  exécute Qwen 2.5.

- **Tunnel Sécurisé (Ngrok) :** Établit une liaison HTTP/HTTPS chiffrée
  entre le local et l'instance distante.

# Impact Technique et Bénéfices Métiers

L'implémentation de cette stratégie hybride offre des avantages
quantifiables pour l'exploitation quotidienne de la plateforme **Waraq**
:

- **Gain de Temps de Traitement :** Traitement de la majorité du flux
  documentaire en quelques millisecondes grâce aux Niveaux 1 et 2,
  réservant l'appel IA aux cas complexes.

- **Traçabilité et Auditabilité :** Chaque décision est enregistrée avec
  sa justification, son score de confiance et ses métadonnées
  d'exécution.

- **Scalabilité :** L'apprentissage continu par injection de contexte
  permet une augmentation organique de la précision au fur et à mesure
  de l'utilisation.
