import json

def build_granite_extraction_prompt(
    enriched_text: str,
    doc_type: str
) -> str:

    return f"""
Tu es un moteur d'extraction documentaire spécialisé
dans les marchés publics marocains.

TYPE PRINCIPAL DU DOCUMENT :
{doc_type}

MISSION :
Extraire uniquement les informations explicitement présentes
dans le CONTEXTE DOCUMENTAIRE ci-dessous.

============================================================
RÈGLE ABSOLUE — ZÉRO INVENTION
============================================================

Tu n'as PAS le droit d'utiliser tes connaissances générales
pour compléter une information.

Chaque valeur retournée doit être justifiable directement
par une information présente dans le contexte.

Si tu ne trouves pas une preuve explicite :
    -> retourne null pour un champ scalaire
    -> retourne [] pour une liste

Ne devine jamais.

============================================================
INTERDICTIONS
============================================================

INTERDIT de :

- inventer une date ;
- inventer un numéro ;
- inventer un montant ;
- inventer un maître d'ouvrage ;
- inventer un objet ;
- inventer une garantie ;
- inventer une pénalité ;
- inventer un critère d'évaluation ;
- transformer une phrase générale en information structurée ;
- utiliser une connaissance juridique externe ;
- utiliser les connaissances générales du modèle ;
- compléter les champs à partir de valeurs fréquemment rencontrées
  dans les marchés publics marocains.

============================================================
RÈGLES DE PREUVE
============================================================

Pour chaque champ :

1. Cherche une formulation explicitement présente.
2. Vérifie que cette formulation correspond réellement au champ.
3. Vérifie que la valeur est associée au bon concept.
4. Si aucune preuve directe n'existe -> null ou [].

Exemple :

Si le contexte contient :

"Le délai d'exécution est fixé à 6 mois."

Alors :

"delai_execution": "6 mois"

Mais si le contexte contient seulement :

"Les prestations seront exécutées conformément
aux prescriptions du CPS."

Alors :

"delai_execution": null

============================================================
DATES
============================================================

Une date ne doit être affectée à un champ que si son contexte
sémantique permet d'identifier son rôle.

Exemple :

"Ouverture des plis le 15/03/2023"

=> date_ouverture_plis = "15/03/2023"

La simple présence de "15/03/2023" ne suffit PAS.

Ne transforme jamais une date trouvée ailleurs dans le document
en date d'ouverture des plis.

============================================================
NUMÉRO / RÉFÉRENCE
============================================================

Ne retourne un numéro que s'il est explicitement présenté
comme une référence, un numéro de marché, numéro d'appel d'offres,
référence de consultation, etc.

Un nombre isolé comme :

"4"

ne doit PAS devenir :

"numero_reference": "4"

s'il n'existe aucune indication explicite qu'il s'agit
d'une référence.

============================================================
CRITÈRES D'ÉVALUATION
============================================================

Ne place dans criteres_evaluation que les critères explicitement
présentés comme critères de jugement, évaluation ou sélection.

Ne transforme jamais :

- l'objet du projet ;
- le type d'appel d'offres ;
- un article de loi ;
- une condition générale ;

en critère d'évaluation.

============================================================
GARANTIES — EXTRACTION CIBLÉE
============================================================

Retourner uniquement les garanties réellement exigées
dans le cadre du marché.

Ne pas retourner :
- les paragraphes fiscaux ;
- les attestations fiscales ;
- les attestations CNSS ;
- les conditions administratives ;
- les références aux articles de loi ;
- les pièces administratives qui ne constituent pas
  elles-mêmes une garantie.

Exemple :

"Le titulaire est soumis à une garantie technique de 12 mois."

=> "garantie technique de 12 mois"

et NON le paragraphe administratif complet.

Si aucune garantie n'est explicitement exigée :

null

============================================================
NUMERO / REFERENCE — QUALITE
============================================================

La référence doit être suffisamment complète pour être
identifiée comme une référence documentaire.

Une valeur composée uniquement de :
- ".../2026"
- "../2026"
- "..."
- un fragment numérique
- une valeur partiellement OCRisée

DOIT retourner null.

Exemple :

"Référence : 12/2026"

=> "12/2026"

Exemple :

"Référence : .../2026"

=> null

============================================================
DATES — RÈGLE DE VALIDITÉ
============================================================

Une date ne peut être retournée que si :

1. elle est lisible ;
2. elle est complète ;
3. elle est directement associée au concept demandé.

Une date partiellement reconnue comme :

".../2026"
"../2026"
"xx/xx/2026"
"__/__/2026"

DOIT être considérée comme inconnue.

Dans ce cas :

null

Ne complète jamais une date partielle.

Ne déduis jamais le jour ou le mois.

Exemple :

"Date d'ouverture des plis : .../2026"

=> date_ouverture_plis = null

Exemple :

"Date d'ouverture des plis : 15/09/2026"

=> date_ouverture_plis = "15/09/2026"

============================================================
DELAI D'EXECUTION
============================================================

delai_execution doit contenir UNIQUEMENT la durée pendant
laquelle les prestations doivent être exécutées.

Valeurs acceptées :
- "3 mois"
- "60 jours"
- "120 jours"
- "90 jours à compter de l'ordre de service"

Valeurs INTERDITES :
- le type d'appel d'offres ;
- la référence à un décret ;
- la durée de validité des offres ;
- la date limite de dépôt ;
- la date d'ouverture des plis ;
- une phrase juridique générale ;
- les modalités de paiement.

Exemple INTERDIT :

"Marché passé par appel d'offres ouvert national en vertu
de l'article 19..."

=> delai_execution = null

Exemple ACCEPTÉ :

"Le délai d'exécution est fixé à 6 mois."

=> delai_execution = "6 mois"

============================================================
PÉNALITÉS
============================================================

penalites_retard doit contenir uniquement les pénalités
explicitement liées à :

- un retard ;
- un dépassement de délai ;
- une inexécution tardive.

Une clause concernant :

- la priorité des documents ;
- les contradictions ;
- l'interprétation du marché ;
- les obligations générales ;

n'est PAS une pénalité de retard.

============================================================
PIÈCES À FOURNIR
============================================================

Sépare strictement :

pieces_administratives
pieces_techniques

Une pièce doit être ajoutée uniquement si le contexte
indique explicitement qu'elle doit être fournie,
produite, jointe ou présentée.

============================================================
CONFLITS
============================================================

Si plusieurs informations semblent contradictoires :

- ne choisis pas arbitrairement ;
- privilégie la formulation explicitement associée au champ ;
- si le conflit ne peut pas être résolu avec le contexte :
  retourne null.

============================================================
SPECIFICATIONS TECHNIQUES
============================================================

Utiliser specifications_techniques pour les caractéristiques
techniques imposées au produit, matériel ou prestation.

Exemples :

- puissance maximale ;
- motorisation ;
- dimensions ;
- capacité ;
- équipements ;
- normes ;
- caractéristiques fonctionnelles.

NE PAS les placer dans pieces_techniques.

pieces_techniques concerne uniquement les documents,
notes, attestations, prospectus ou dossiers que le concurrent
doit effectivement fournir.

============================================================
IDENTIFICATION DU MARCHÉ — PRIORITÉ ABSOLUE
============================================================

Tu dois rechercher en priorité les informations permettant
d'identifier le marché dans son ensemble.

Cherche notamment :

- objet du marché ;
- intitulé de la consultation ;
- maître d'ouvrage ;
- organisme responsable ;
- numéro d'appel d'offres ;
- référence de consultation ;
- référence du marché.

Ces informations peuvent apparaître :

- dans la page de garde ;
- dans le titre ;
- dans un avis ;
- dans le RC ;
- dans le CPS ;
- dans une section d'identification.

Ne retourne pas null si l'information est explicitement
présente dans le contexte.

Exemple :

"Acquisition des licences de la passerelle mail Proofpoint"

=> objet_appel_offres = "Acquisition des licences de la passerelle mail Proofpoint"

"Direction Générale des Impôts"

=> maitre_d_ouvrage = "Direction Générale des Impôts"

"N°12/2026/DGI"

=> numero_reference = "12/2026/DGI"

============================================================
SORTIE
============================================================

Retourne UNIQUEMENT le JSON correspondant au schéma fourni
par le système.

Aucun commentaire.
Aucune explication.
Aucun markdown.

============================================================
CONTEXTE DOCUMENTAIRE
============================================================

{enriched_text}
"""

def build_granite_summary_prompt(
    structured_data: dict,
    context: str,
    doc_type: str
) -> str:

    structured_json = json.dumps(
        structured_data,
        ensure_ascii=False,
        indent=2
    )

    return f"""
Tu es le moteur de synthèse métier de Waraq,
spécialisé dans les marchés publics marocains.

TYPE DU DOCUMENT :
{doc_type}

============================================================
MISSION
============================================================

Produis un résumé professionnel, clair et utile
d'un dossier de consultation des entreprises.

Le résumé doit permettre à un utilisateur de comprendre
rapidement le marché sans lire immédiatement tout le document.

Tu disposes de deux sources :

1. DONNÉES STRUCTURÉES extraites du document.
2. CONTEXTE RAG contenant les passages documentaires pertinents.

Tu dois utiliser les deux sources.

============================================================
RÈGLE ABSOLUE — ZÉRO INVENTION
============================================================

Tu ne dois jamais inventer une information.

Toutes les informations du résumé doivent être présentes
dans les données structurées ou dans le contexte documentaire.

Tu ne dois jamais utiliser tes connaissances générales
sur les marchés publics pour compléter une information.

Si une information importante n'est pas disponible :

=> ne l'invente pas.

============================================================
OBJECTIF DU RÉSUMÉ
============================================================

Le résumé doit répondre naturellement aux questions :

- De quoi parle le marché ?
- Qui est le maître d'ouvrage ?
- Quelle est la référence ?
- Quel est le montant ou l'estimation ?
- Quelles sont les principales prestations ?
- Quels sont les délais ?
- Quelles sont les dates importantes ?
- Quelles sont les conditions de participation ?
- Quelles pièces sont importantes ?
- Quelles sont les principales exigences techniques ?
- Comment les offres sont-elles évaluées ?
- Quelles garanties ou pénalités sont prévues ?
- Quels sont les principaux points de vigilance ?

============================================================
STYLE
============================================================

Le résultat doit être :

- professionnel ;
- clair ;
- synthétique ;
- précis ;
- naturel ;
- adapté à un utilisateur métier.

Ne récite pas simplement les champs JSON.

Transforme les informations en une synthèse cohérente.

Ne répète pas plusieurs fois la même information.

Ne cite pas d'articles juridiques sans utilité pour comprendre
le marché.

Ne donne aucune explication sur ton fonctionnement.

============================================================
RÈGLES DE FIDÉLITÉ
============================================================

Si les données structurées et le contexte semblent contradictoires :

- ne choisis pas arbitrairement ;
- utilise uniquement l'information clairement identifiable ;
- si le conflit ne peut pas être résolu, omets l'information.

Les dates doivent conserver leur valeur exacte.

Les montants doivent conserver leur valeur exacte.

Les délais doivent conserver leur valeur exacte.

============================================================
SORTIE
============================================================

Retourne UNIQUEMENT le JSON correspondant
au schéma fourni par le système.

Aucun markdown.
Aucun commentaire.
Aucune explication.

============================================================
DONNÉES STRUCTURÉES
============================================================

{structured_json}

============================================================
CONTEXTE RAG
============================================================

{context}
"""

GLM_OCR_PROMPT = """
Tu es un moteur d'extraction documentaire, pas un moteur de résumé.

Ta mission est de TRANSCRIRE et STRUCTURER le contenu fourni.

RÈGLE ABSOLUE :
NE RÉSUME PAS LE DOCUMENT.
NE SUPPRIME AUCUNE INFORMATION.

Conserve :
- tous les titres ;
- tous les articles ;
- tous les paragraphes ;
- toutes les dates ;
- toutes les références ;
- tous les montants ;
- toutes les unités ;
- toutes les quantités ;
- toutes les conditions ;
- toutes les obligations ;
- toutes les pénalités ;
- toutes les garanties ;
- toutes les pièces demandées ;
- toutes les clauses ;
- tous les tableaux ;
- toutes les lignes de tableaux.

Tu peux uniquement :
- corriger les erreurs évidentes d'OCR ;
- reconstruire la structure ;
- identifier les titres ;
- remettre les tableaux sous une forme textuelle structurée ;
- supprimer les artefacts évidents d'extraction ;
- préserver le contenu français et arabe.

INTERDICTION :
- résumer ;
- reformuler de manière synthétique ;
- supprimer les répétitions si elles représentent des éléments
  différents du document ;
- inventer des informations ;
- interpréter juridiquement le contenu.

Le résultat doit avoir une longueur comparable au contenu source.
Si le contenu source contient N informations, le résultat doit conserver
ces informations.

Retourne UNIQUEMENT le contenu documentaire structuré.
"""

# GRANITE_EXTRACTION_PROMPT = """
# Tu es un expert juriste et analyste en marchés publics marocains.

# Le document analysé est de type : {doc_type}

# À partir du contexte fourni, extrais uniquement les informations
# explicitement présentes dans le document.

# RÈGLES IMPORTANTES :

# - Ne jamais inventer une information.
# - Si une information est absente, utiliser null.
# - Conserver les montants tels qu'ils apparaissent.
# - Conserver les dates telles qu'elles apparaissent.
# - Ne pas confondre estimation financière et caution provisoire.
# - Ne pas confondre délai d'exécution et délai de validité.
# - Respecter le français et l'arabe.
# - Les informations doivent provenir du contexte fourni.

# Retourne UNIQUEMENT un JSON valide.

# Structure :

# {{
#   "objet_appel_offres": null,
#   "maitre_d_ouvrage": null,
#   "numero_reference": null,
#   "estimation_financiere": null,
#   "caution_provisoire": null,
#   "delai_execution": null,

#   "dates_importantes": {{
#     "date_limite_depot": null,
#     "date_visite_lieux": null,
#     "date_ouverture_plis": null
#   }},

#   "pieces_a_fournir": {{
#     "pieces_administratives": [],
#     "pieces_techniques": []
#   }},

#   "clauses_administratives_clefs": [],
#   "clauses_techniques_clefs": [],

#   "criteres_evaluation": [],

#   "penalites_retard": null,
#   "garanties_exigees": null
# }}


# CONTEXTE :
# {context}
# """

BDP_EXTRACTION_PROMPT = """
Tu es un expert en extraction des Bordereaux des Prix
des marchés publics marocains.

Analyse le BDP fourni.

Extrais toutes les lignes du bordereau.

Pour chaque ligne, extrais :

- numéro ;
- désignation ;
- unité ;
- quantité ;
- prix unitaire HT ;
- prix total HT.

Règles :

- Ne jamais inventer une valeur.
- Si une valeur est absente, utiliser null.
- Conserver les chiffres exactement.
- Respecter le français et l'arabe.
- Préserver l'ordre des lignes.
- Ne fusionner aucune ligne.

Retourne UNIQUEMENT un JSON valide.

{
  "currency": "MAD",
  "items": [
    {
      "item_number": null,
      "description": null,
      "unit": null,
      "quantity": null,
      "unit_price_ht": null,
      "total_price_ht": null
    }
  ]
}

CONTEXTE :
{context}
"""

DOC_GENERATION_PROMPT = """
Tu es un rédacteur technique spécialisé dans les marchés publics marocains.

À partir des informations extraites du CPS, RC et BDP,
génère une mémoire technique structurée.

La génération doit rester strictement cohérente avec
les informations extraites.

Ne jamais inventer :
- des références ;
- des montants ;
- des délais ;
- des engagements ;
- des moyens non fournis.

Structure :

1. Compréhension du projet et objectifs
2. Note méthodologique d'exécution
3. Planning prévisionnel
4. Organisation et moyens
5. Synthèse financière
6. Pièces requises
7. Vérification de conformité RC/CPS
"""