# import logging, requests, time, json, re
# from backend.app.config import settings

# # Configuration locale du logger
# logger = logging.getLogger("app.ai_processor.llm_analyzer")

# OLLAMA_URL = f"{settings.OLLAMA_BASE_URL}/api/generate"
# MODEL_NAME = settings.OLLAMA_MODEL

# def classifier_texte_document(texte: str, contexte_few_shot: str = "") -> tuple[str, str, dict]:
#     """
#     Analyse le texte et retourne un tuple : (TYPE_DETECTE, EXPLICATION, METRIQUES)
#     """
#     if not texte.strip():
#         logger.warning("Texte vide reçu pour la classification globale.")
#         return "INCONNU", "Le document ne contient aucun texte exploitable.", {}

#     # Si c'un fichier DAO/CAD sans texte
#     if texte.startswith("FICHIER_TECHNIQUE_DAO_"):
#         ext_type = texte.split("_")[-1]
#         return "SCHEMA_TOPOLOGIQUE", f"Fichier de dessin technique CAO/DAO ({ext_type}).", {}

#     # Pour un document complet : on prend le début (ex: 2000 chars) et la fin (ex: 1000 chars)
#     # afin de capturer l'en-tête (Avis/CPS/RC) et les signatures/bordereaux à la fin.
#     if len(texte) > 3500:
#         extrait_analyse = f"{texte[:2000]}\n\n[... CONTENU INTERMÉDIAIRE SERPENTÉ ...]\n\n{texte[-1500:]}"
#     else:
#         extrait_analyse = texte
    
#     prompt = f"""{contexte_few_shot}

# Analyse cet extrait de document de marché public au Maroc.
# Détermine sa nature exacte parmi : AVIS_FRANCAIS, AVIS_ARABE, AVIS, RC, CPS, ACTE_ENGAGEMENT, DECLARATION_HONNEUR, BORDEREAU_PRIX, SCHEMA_TOPOLOGIQUE, DECOUPAGE_PDF_AUTOMATIQUE, AUTRE.
# Si le document contient plusieurs pièces distinctes assemblées (ex: un RC suivi d'un CPS ou un Bordereau), indique "DECOUPAGE_PDF_AUTOMATIQUE".

# Tu dois répondre UNIQUEMENT sous la forme d'un objet JSON strict avec ces 5 clés exactes : 
# - "type": Le code de la catégorie parmi la liste ci-dessus.
# - "raison": Une phrase concise en français expliquant pourquoi.
# - "confidence": Une note entière de 1 (très incertain) à 5 (certain à 100%).
# - "keywords": Une liste de 3 ou 4 mots-clés décisifs trouvés dans le texte qui justifient ce choix.
# - "language": Le code langue détecté ("fr", "ar").

# Document :
# {extrait_analyse}"""

#     logger.info(f"Envoi d'une requête de classification globale à Ollama ({MODEL_NAME})...")
#     start_time = time.time()
#     try:
#         reponse = requests.post(
#             OLLAMA_URL, 
#             json={'model': MODEL_NAME, 'prompt': prompt, 'stream': False, 'format': 'json'}, 
#             timeout=None  
#         )
#         reponse.raise_for_status()
        
#         reponse_json_data = reponse.json()
#         raw_res = reponse_json_data['response'].strip()
        
#         # Extraction robuste du bloc JSON situé entre { et }
#         match = re.search(r'\{.*\}', raw_res, re.DOTALL)
#         if match:
#             raw_res = match.group(0)
            
#         data = json.loads(raw_res)
#         tipo = str(data.get("type", "INCONNU")).strip().upper()
#         raison = str(data.get("raison", "Aucune explication fournie.")).strip()
        
#         duration = time.time() - start_time
#         logger.info(f"Classification IA en {duration:.2f}s : {tipo}")

#         # === CORRECTION DES VARIABLES & INTÉGRATION DES MÉTRIQUES ===
#         metrics = {
#             "model": MODEL_NAME,
#             "confidence_score": data.get("confidence"),      
#             "extracted_keywords": data.get("keywords", []),   
#             "detected_language": data.get("language", "fr"), 
#             "text_length_chars": len(texte),                  
#             "text_word_count": len(texte.split()),            
#             "is_short_text": len(texte.split()) < 20,         
#             "has_uncertainty_keywords": any(w in raison.lower() for w in ["incertain", "doute", "hésite", "ambigu", "inconnu", "pas clair"]),
#             "ollama_total_duration": reponse_json_data.get("total_duration"),
#             "load_duration": reponse_json_data.get("load_duration"),
#             "prompt_tokens": reponse_json_data.get("prompt_eval_count"),
#             "generated_tokens": reponse_json_data.get("eval_count"),
#             "validation_status": "PENDING",  
#             "is_correct": None,              
#             "corrected_type": None           
#         }
        
#         return tipo, raison, metrics

#     # === CORRECTION DES RETOURS D'ERREUR (Ajout du {} vide pour éviter le crash au unpacking) ===
#     except json.JSONDecodeError:
#         logger.error("Le LLM n'a pas retourné un JSON valide.")
#         return "INCONNU", "Format de réponse invalide.", {}
#     except Exception as e:
#         logger.error(f"Échec de l'appel Ollama : {str(e)}", exc_info=True)
#         return "INCONNU", f"Erreur système : {str(e)}", {}

# def classifier_page_pour_decoupage(texte_page: str) -> str:
#     """Analyse rapide par mots-clés d'une page individuelle pour le découpage PDF."""
#     if not texte_page or not texte_page.strip():
#         return "INCONNU"

#     # Nettoyage : minuscules et suppression des retours à la ligne / espaces multiples
#     txt = " ".join(texte_page.lower().split())

#     if any(k in txt for k in ["bordereau des prix", "b.p.s", "prix unitaire", "detail estimatif", "détail estimatif"]):
#         return "BORDEREAU_PRIX"
#     elif any(k in txt for k in ["reglement de la consultation", "règlement de la consultation", " r.c ", " r.c."]):
#         return "RC"
#     elif any(k in txt for k in ["cahier des prescriptions speciales", "cahier des prescriptions spéciales", " c.p.s ", " c.p.s."]):
#         return "CPS"
#     elif any(k in txt for k in ["acte d'engagement", "acte d’engagement"]):
#         return "ACTE_ENGAGEMENT"
#     elif any(k in txt for k in ["declaration sur l'honneur", "déclaration sur l'honneur"]):
#         return "DECLARATION_HONNEUR"
#     elif any(k in txt for k in ["avis de concours", "avis d'appel d'offres", "avis d’appel d’offres", "avis d'appel d'offre"]):
#         return "AVIS"

#     return "INCONNU"
    
    
import logging, requests, time, json, re, torch, pypdf
from backend.app.config import settings

logger = logging.getLogger("app.ai_processor.llm_analyzer")

OLLAMA_URL = f"{settings.OLLAMA_BASE_URL}/api/generate"
MODEL_NAME = settings.OLLAMA_MODEL


# ==========================================
# 1. UTILITAIRES HARDWARE & LECTURE PDF
# ==========================================

def obtenir_device_execution() -> str:
    """Vérifie la disponibilité d'un GPU CUDA."""
    if torch.cuda.is_available():
        device = "cuda"
        logger.info(f"GPU détecté : {torch.cuda.get_device_name(0)} - Exécution sur GPU.")
    else:
        device = "cpu"
        logger.info("Aucun GPU détecté - Bascule sur CPU.")
    return device
    
# Initialisation du device directement au niveau du module si besoin
DEVICE = obtenir_device_execution()

def extraire_texte_par_lots(path_pdf: str, taille_lot: int = 10) -> list[dict]:
    """Lit un PDF par paquets de `taille_lot` pages."""
    lots_texte = []
    try:
        reader = pypdf.PdfReader(path_pdf)
        total_pages = len(reader.pages)

        for i in range(0, total_pages, taille_lot):
            pages_lot = reader.pages[i : i + taille_lot]
            texte_lot = ""
            for idx_page, page in enumerate(pages_lot):
                txt = page.extract_text() or ""
                texte_lot += f"\n--- Page {i + idx_page + 1} ---\n" + txt

            lots_texte.append({
                "lot_index": (i // taille_lot) + 1,
                "page_debut": i + 1,
                "page_fin": min(i + taille_lot, total_pages),
                "texte": texte_lot
            })
    except Exception as e:
        logger.error(f"Échec de la lecture du PDF {path_pdf}: {e}")

    return lots_texte


# ==========================================
# 2. CLASSIFICATION LLM (OLLAMA)
# ==========================================


def verifier_ou_classifier_par_llm(texte: str, type_primitif_detecte: str = None, contexte_few_shot: str = "") -> dict:
    """
    Vérifie si le type primitif détecté est valide via le LLM.
    Si aucun type primitif n'est fourni, lance une classification complète.
    """
    if not type_primitif_detecte or type_primitif_detecte == "INCONNU":
        tipo, raison, metrics = classifier_texte_document(texte, contexte_few_shot)
        return {
            "est_valide": tipo != "INCONNU",
            "type_confirme": tipo,
            "justification": raison,
            "langue": metrics.get("detected_language", "fr")
        }

    # Prompt de confirmation si une règle primitive a déjà trouvé un type
    prompt = f"""
Voici un extrait de document de marché public au Maroc.
Une règle basée sur le nom du fichier ou des mots-clés suggère le type : {type_primitif_detecte}.

Analyse l'extrait ci-dessous et confirme si ce type est exact.

Document :
{texte[:2500]}

Réponds UNIQUEMENT sous forme d'un objet JSON strict avec ces 4 clés :
- "est_valide": boolean (true si le texte correspond bien à {type_primitif_detecte}, false sinon)
- "type_confirme": string (le type confirmé, ou le vrai type si invalide)
- "justification": string (courte explication de 1 phrase)
- "langue": string ("fr" ou "ar")
"""
    try:
        reponse = requests.post(
            OLLAMA_URL,
            json={'model': MODEL_NAME, 'prompt': prompt, 'stream': False, 'format': 'json'},
            timeout=60
        )
        reponse.raise_for_status()
        raw_res = reponse.json().get('response', '').strip()
        
        match = re.search(r'\{.*\}', raw_res, re.DOTALL)
        if match:
            raw_res = match.group(0)

        data = json.loads(raw_res)
        return {
            "est_valide": bool(data.get("est_valide", False)),
            "type_confirme": str(data.get("type_confirme", type_primitif_detecte)).strip().upper(),
            "justification": str(data.get("justification", "Validation primitive.")),
            "langue": str(data.get("langue", "fr")).lower()
        }
    except Exception as e:
        logger.error(f"Échec lors de la vérification LLM de la primitive : {e}")
        return {
            "est_valide": False,
            "type_confirme": "INCONNU",
            "justification": f"Erreur de validation LLM : {str(e)}",
            "langue": "fr"
        }

def classifier_texte_document(texte: str, contexte_few_shot: str = "") -> tuple[str, str, dict]:
    """Analyse le texte via Ollama et retourne : (TYPE_DETECTE, EXPLICATION, METRIQUES)"""
    if not texte.strip():
        logger.warning("Texte vide reçu pour la classification.")
        return "INCONNU", "Le document ne contient aucun texte exploitable.", {}

    if texte.startswith("FICHIER_TECHNIQUE_DAO_"):
        ext_type = texte.split("_")[-1]
        return "SCHEMA_TOPOLOGIQUE", f"Fichier de dessin technique CAO/DAO ({ext_type}).", {}

    # Extraction en-tête / fin pour limiter la taille du context window
    if len(texte) > 3500:
        extrait_analyse = f"{texte[:2000]}\n\n[... CONTENU INTERMÉDIAIRE SERPENTÉ ...]\n\n{texte[-1500:]}"
    else:
        extrait_analyse = texte

    prompt = f"""{contexte_few_shot}

Analyse cet extrait de document de marché public au Maroc.
Détermine sa nature exacte parmi : AVIS_FRANCAIS, AVIS_ARABE, AVIS, RC, CPS, ACTE_ENGAGEMENT, DECLARATION_HONNEUR, BORDEREAU_PRIX, SCHEMA_TOPOLOGIQUE, DECOUPAGE_PDF_AUTOMATIQUE, AUTRE.
Si le document contient plusieurs pièces distinctes assemblées (ex: un RC suivi d'un CPS ou un Bordereau), indique "DECOUPAGE_PDF_AUTOMATIQUE".

Tu dois répondre UNIQUEMENT sous la forme d'un objet JSON strict avec ces 5 clés exactes : 
- "type": Le code de la catégorie parmi la liste ci-dessus.
- "raison": Une phrase concise en français expliquant pourquoi.
- "confidence": Une note entière de 1 (très incertain) à 5 (certain à 100%).
- "keywords": Une liste de 3 ou 4 mots-clés décisifs trouvés dans le texte qui justifient ce choix.
- "language": Le code langue détecté ("fr", "ar").

Document :
{extrait_analyse}"""

    logger.info(f"Envoi de la requête de classification à Ollama ({MODEL_NAME})...")
    start_time = time.time()
    try:
        reponse = requests.post(
            OLLAMA_URL,
            json={'model': MODEL_NAME, 'prompt': prompt, 'stream': False, 'format': 'json'},
            timeout=120
        )
        reponse.raise_for_status()

        reponse_json_data = reponse.json()
        raw_res = reponse_json_data.get('response', '').strip()

        match = re.search(r'\{.*\}', raw_res, re.DOTALL)
        if match:
            raw_res = match.group(0)

        data = json.loads(raw_res)
        tipo = str(data.get("type", "INCONNU")).strip().upper()
        raison = str(data.get("raison", "Aucune explication fournie.")).strip()

        duration = time.time() - start_time
        logger.info(f"Classification IA en {duration:.2f}s : {tipo}")

        metrics = {
            "model": MODEL_NAME,
            "confidence_score": data.get("confidence"),
            "extracted_keywords": data.get("keywords", []),
            "detected_language": data.get("language", "fr"),
            "text_length_chars": len(texte),
            "text_word_count": len(texte.split()),
            "is_short_text": len(texte.split()) < 20,
            "has_uncertainty_keywords": any(w in raison.lower() for w in ["incertain", "doute", "hésite", "ambigu", "inconnu", "pas clair"]),
            "ollama_total_duration": reponse_json_data.get("total_duration"),
            "load_duration": reponse_json_data.get("load_duration"),
            "prompt_tokens": reponse_json_data.get("prompt_eval_count"),
            "generated_tokens": reponse_json_data.get("eval_count"),
            "validation_status": "PENDING",
            "is_correct": None,
            "corrected_type": None
        }

        return tipo, raison, metrics

    except json.JSONDecodeError:
        logger.error("Le LLM n'a pas retourné un JSON valide.")
        return "INCONNU", "Format de réponse invalide.", {}
    except Exception as e:
        logger.error(f"Échec de l'appel Ollama : {str(e)}", exc_info=True)
        return "INCONNU", f"Erreur système : {str(e)}", {}


# ==========================================
# 3. RÈGLES HEURISTIQUES
# ==========================================

def classifier_page_pour_decoupage(texte_page: str) -> str:
    """Analyse rapide par mots-clés d'une page individuelle pour le découpage PDF."""
    if not texte_page or not texte_page.strip():
        return "INCONNU"

    txt = " ".join(texte_page.lower().split())

    if any(k in txt for k in ["bordereau des prix", "b.p.s", "prix unitaire", "detail estimatif", "détail estimatif"]):
        return "BORDEREAU_PRIX"
    elif any(k in txt for k in ["reglement de la consultation", "règlement de la consultation", " r.c ", " r.c."]):
        return "RC"
    elif any(k in txt for k in ["cahier des prescriptions speciales", "cahier des prescriptions spéciales", " c.p.s ", " c.p.s."]):
        return "CPS"
    elif any(k in txt for k in ["acte d'engagement", "acte d’engagement"]):
        return "ACTE_ENGAGEMENT"
    elif any(k in txt for k in ["declaration sur l'honneur", "déclaration sur l'honneur"]):
        return "DECLARATION_HONNEUR"
    elif any(k in txt for k in ["avis de concours", "avis d'appel d'offres", "avis d’appel d’offres", "avis d'appel d'offre"]):
        return "AVIS"

    return "INCONNU"