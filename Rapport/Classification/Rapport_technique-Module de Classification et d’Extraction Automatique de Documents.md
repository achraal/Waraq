![](Aspose.Words.03b9bf88-82b2-4dfa-aba1-80b5b0659a6d.001.png) ![](Aspose.Words.03b9bf88-82b2-4dfa-aba1-80b5b0659a6d.002.png)

Rapport Technique : Module de Classification et d’Extraction Automatique de Documents\
(Marchés Publics)

Achraf AIT LAHCEN

Juillet 2026

1\. Contexte et Objectifs

Le module a pour objectif d’automatiser la chaîne de traitement des documents admi- nistratifs liés aux marchés publics marocains (Règlement de Consultation - RC, Cahier des Prescriptions Spéciales - CPS, Bordereau des Prix - BDR, Acte d’Engagement - AE).

Le système doit être capable de :

1. Identifier et classifier de manière autonome la nature du document soumis.
1. Extraire les métadonnées clés requises pour la soumission.
1. Mettre à jour la base de données et archiver proprement les fichiers (renommage automatisé).
1. Alimenter la génération de documents légaux (Acte d’engagement et Déclaration d’honneur).
2. Contraintes Techniques et Choix d’Architecture
1. Gestion de la Réalité du Terrain (Scans, Inclinaisons, Bilin- guisme)

Les documents de marchés publics au Maroc présentent trois défis majeurs : la nature scannée des PDF (images non textuelles), le désalignement ou l’inclinaison des pages, et l’usage fréquent du bilinguisme (Français / Arabe).

Solution retenue : Un pipeline séquentiel OCR + LLM. L’OCR fait office "d’yeux" pour extraire le texte brut, tandis que le LLM fait office "de cerveau" pour comprendre le sens, classifier et extraire les données.

2. Contraintes Matérielles (Infrastructure Légère)

Pour garantir une exécution en local sans dépendance financière à des API Cloud et pour respecter l’usage de ressources matérielles limitées, le choix s’est porté sur des technologies open-source hautement optimisées :

- OCR : PaddleOCR – Sélectionné pour sa légèreté, sa gestion native de l’arabe et son module de classification d’angle automatique permettant de redresser les textes penchés.
- LLM : Qwen2.5-3B (via Ollama) – Préféré à d’autres petits modèles (comme Phi-3) pour sa supériorité multilingue, offrant une compréhension parfaite du français admi- nistratif et de la langue arabe juridique sur des architectures matérielles CPU/GPU standards.
3. Spécifications du Pipeline de Traitement (Workflow)

Le flux de traitement est structuré comme suit :

[Document PDF]

|

v

+--------------------------------------+

| 1. Extraction & Redressement (OCR) | -> Exécution via PaddleOCR

| | (Correction automatique de l’angle) +----------------+---------------------+

| (Texte brut extrait)

v

+--------------------------------------+

| 2. Classification & Extraction (LLM) | -> Requête unique au format JSON strict | | via Qwen2.5 (Ollama) +----------------+---------------------+

| (Données structurées : Type, Client, Objet, Cautionnement)

v

+--------------------------------------+

| 3. Actions Automatiques Post-Analyse | -> Renommage physique du fichier

| | -> ‘UPDATE‘ en base de données +--------------------------------------+

Le pipeline repose sur trois étapes clés :

1. Extraction & Redressement (OCR) : Exécution via PaddleOCR.
1. Classification & Extraction (LLM) : Requête unique au format JSON strict via Qwen2.5.
1. Actions Automatiques Post-Analyse : Renommage physique et mise à jour BDD.
4. Gestion des Documents Hybrides (Multi-Documents / Segmentation)

Afin de pallier le risque d’un fichier unique contenant plusieurs pièces jointes fusionnées (ex : un scan continu contenant le RC puis le CPS), deux strategies barrières sont retenues :

1. Stratégie UX (Prioritaire) : Interface de depot segmentee par document, combinée à une validation par le LLM (le système lève une alerte si le contenu de la case "RC" est détecté comme un "CPS").
1. Stratégie Algorithmique (Évolution) : Analyse textuelle page par page pour détecter les ruptures de catégories ou l’apparition de pages de garde de chapitres via expressions régulières (Regex).

5\. Indicateurs de Succès et Rentabilité

1. Gain de Temps : Reduction du temps de traitement d’un dossier de 45 minutes (saisie manuelle) à moins de 10 secondes (pipeline automatisé).
1. Fiabilité : Élimination des erreurs de recopie humaine dans l’acte d’engagement grâce à l’injection directe des variables extraites par le LLM dans des templates .docx pre- formates.
1. Indépendance financière : Coût d’exploitation nul à l’utilisation grâce au deploie- ment des modeles en local.
3
