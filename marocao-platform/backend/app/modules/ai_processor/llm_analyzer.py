import logging, requests, time, json, re
from backend.app.config import settings

# Configuration locale du logger
logger = logging.getLogger("app.ai_processor.llm_analyzer")

OLLAMA_URL = f"{settings.OLLAMA_BASE_URL}/api/generate"
MODEL_NAME = settings.OLLAMA_MODEL

def classifier_texte_document(texte: str, contexte_few_shot: str = "") -> tuple[str, str, dict]:
    """
    Analyse le texte et retourne un tuple : (TYPE_DETECTE, EXPLICATION, METRIQUES)
    """
    if not texte.strip():
        logger.warning("Texte vide reçu pour la classification globale.")
        return "INCONNU", "Le document ne contient aucun texte exploitable.", {}

    # Si c'un fichier DAO/CAD sans texte
    if texte.startswith("FICHIER_TECHNIQUE_DAO_"):
        ext_type = texte.split("_")[-1]
        return "SCHEMA_TOPOLOGIQUE", f"Fichier de dessin technique CAO/DAO ({ext_type}).", {}

    # Pour un document complet : on prend le début (ex: 2000 chars) et la fin (ex: 1000 chars)
    # afin de capturer l'en-tête (Avis/CPS/RC) et les signatures/bordereaux à la fin.
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

    logger.info(f"Envoi d'une requête de classification globale à Ollama ({MODEL_NAME})...")
    start_time = time.time()
    try:
        reponse = requests.post(
            OLLAMA_URL, 
            json={'model': MODEL_NAME, 'prompt': prompt, 'stream': False, 'format': 'json'}, 
            timeout=None  
        )
        reponse.raise_for_status()
        
        reponse_json_data = reponse.json()
        raw_res = reponse_json_data['response'].strip()
        
        # Extraction robuste du bloc JSON situé entre { et }
        match = re.search(r'\{.*\}', raw_res, re.DOTALL)
        if match:
            raw_res = match.group(0)
            
        data = json.loads(raw_res)
        tipo = str(data.get("type", "INCONNU")).strip().upper()
        raison = str(data.get("raison", "Aucune explication fournie.")).strip()
        
        duration = time.time() - start_time
        logger.info(f"Classification IA en {duration:.2f}s : {tipo}")

        # === CORRECTION DES VARIABLES & INTÉGRATION DES MÉTRIQUES ===
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

    # === CORRECTION DES RETOURS D'ERREUR (Ajout du {} vide pour éviter le crash au unpacking) ===
    except json.JSONDecodeError:
        logger.error("Le LLM n'a pas retourné un JSON valide.")
        return "INCONNU", "Format de réponse invalide.", {}
    except Exception as e:
        logger.error(f"Échec de l'appel Ollama : {str(e)}", exc_info=True)
        return "INCONNU", f"Erreur système : {str(e)}", {}

def classifier_page_pour_decoupage(texte_page: str) -> str:
    """Analyse rapide par mots-clés d'une page individuelle pour le découpage PDF."""
    if not texte_page or not texte_page.strip():
        return "INCONNU"

    # Nettoyage : minuscules et suppression des retours à la ligne / espaces multiples
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