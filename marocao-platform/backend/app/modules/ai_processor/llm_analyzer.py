# import logging, requests, time, json
# from backend.app.config import settings

# # Configuration locale du logger
# logger = logging.getLogger("app.ai_processor.llm_analyzer")

# OLLAMA_URL = f"{settings.OLLAMA_BASE_URL}/api/generate"
# MODEL_NAME = settings.OLLAMA_MODEL

# def classifier_texte_document(texte: str) -> tuple[str, str]:
#     """
#     Analyse le texte et retourne un tuple : (TYPE_DETECTE, EXPLICATION)
#     """
#     if not texte.strip():
#         logger.warning("Texte vide reçu pour la classification globale.")
#         return "INCONNU", "Le document ne contient aucun texte exploitable."
        
#     prompt = f"""Analyse cet extrait de document de marché public au Maroc.
# Détermine sa nature exacte parmi : AVIS_FRANCAIS, AVIS_ARABE, AVIS, RC, CPS, ACTE_ENGAGEMENT, DECLARATION_HONNEUR, BORDEREAU_PRIX, SCHEMA_TOPOLOGIQUE, AUTRE.

# Tu dois répondre UNIQUEMENT sous la forme d'un objet JSON strict avec deux clés : "type" et "raison".
# - "type": Le code de la catégorie parmi la liste ci-dessus (ou "AUTRE" si c'est un schéma, une topologie, ou non listé).
# - "raison": Une phrase concise en français expliquant pourquoi (ex: "Contient des clauses administratives et des cahiers des charges (CPS)", "Présence de coordonnées géographiques et plans de masse sans texte juridique").

# Extrait :
# {texte[:1500]}"""

#     logger.info(f"Envoi d'une requête de classification globale à Ollama ({MODEL_NAME})...")
#     start_time = time.time()
#     try:
#         reponse = requests.post(OLLAMA_URL, json={'model': MODEL_NAME, 'prompt': prompt, 'stream': False}, timeout=15)
#         reponse.raise_for_status()
#         # Nettoyage et parsing du JSON
#         raw_res = reponse.json()['response'].strip()
        
#         # Nettoyage si le LLM ajoute du Markdown autour du JSON
#         if "```json" in raw_res:
#             raw_res = raw_res.split("```json")[1].split("```")[0].strip()
#         elif "```" in raw_res:
#             raw_res = raw_res.split("```")[1].split("```")[0].strip()
            
#         data = json.loads(raw_res)
#         tipo = data.get("type", "INCONNU").strip().upper()
#         raison = data.get("raison", "Aucune explication fournie.")
        
#         duration = time.time() - start_time
#         logger.info(f"Classification IA en {duration:.2f}s : {tipo}")
        
#         return tipo, raison

#     except json.JSONDecodeError:
#         logger.error("Le LLM n'a pas retourné un JSON valide.")
#         return "INCONNU", "Format de réponse invalide."
#     except Exception as e:
#         logger.error(f"Échec de l'appel Ollama : {str(e)}", exc_info=True)
#         return "INCONNU", f"Erreur système : {str(e)}"

#     #     logger.info(f"Réponse brute reçue d'Ollama en {duration:.2f}s : '{res}'")

#     #     for t in ["AVIS_FRANCAIS", "AVIS_ARABE", "AVIS", "RC", "CPS", "ACTE_ENGAGEMENT", "DECLARATION_HONNEUR", "BORDEREAU_PRIX"]:
#     #         if t in res:
#     #             logger.info(f"Classification validée par le LLM : {t}")
#     #             return t
#     # except Exception as e:
#     #     logger.error(f"Échec de l'appel Ollama (Classification globale) : {str(e)}", exc_info=True)
    
#     # logger.warning("L'IA n'a pas pu déterminer une catégorie valide. Retour à 'INCONNU'.")
#     # return "INCONNU"

# def classifier_page_pour_decoupage(texte_page: str) -> str:
#     if not texte_page.strip():
#         return "INCONNU"
        
#     prompt = f"Donne le type de ce contenu de page de marché public marocain parmi (RC, CPS, BORDEREAU_PRIX). Réponds juste le code, sinon réponds INCONNU : {texte_page[:800]}"
#     try:
#         reponse = requests.post(OLLAMA_URL, json={'model': MODEL_NAME, 'prompt': prompt, 'stream': False}, timeout=5)
#         return reponse.json()['response'].strip().upper()
#     except Exception:
#         return "INCONNU"


import logging, requests, time, json, re
from backend.app.config import settings

# Configuration locale du logger
logger = logging.getLogger("app.ai_processor.llm_analyzer")

OLLAMA_URL = f"{settings.OLLAMA_BASE_URL}/api/generate"
MODEL_NAME = settings.OLLAMA_MODEL

# def classifier_texte_document(texte: str) -> tuple[str, str]:
#     """
#     Analyse le texte et retourne un tuple : (TYPE_DETECTE, EXPLICATION)
#     """
#     if not texte.strip():
#         logger.warning("Texte vide reçu pour la classification globale.")
#         return "INCONNU", "Le document ne contient aucun texte exploitable."
        
#     prompt = f"""Analyse cet extrait de document de marché public au Maroc.
# Détermine sa nature exacte parmi : AVIS_FRANCAIS, AVIS_ARABE, AVIS, RC, CPS, ACTE_ENGAGEMENT, DECLARATION_HONNEUR, BORDEREAU_PRIX, SCHEMA_TOPOLOGIQUE, AUTRE.

# Tu dois répondre UNIQUEMENT sous la forme d'un objet JSON strict avec deux clés : "type" et "raison".
# - "type": Le code de la catégorie parmi la liste ci-dessus (ou "AUTRE" si c'est un schéma, une topologie, ou non listé).
# - "raison": Une phrase concise en français expliquant pourquoi (ex: "Contient des clauses administratives et des cahiers des charges (CPS)").

# Extrait :
# {texte[:1500]}"""

#     logger.info(f"Envoi d'une requête de classification globale à Ollama ({MODEL_NAME})...")
#     start_time = time.time()
#     try:
#         reponse = requests.post(
#             OLLAMA_URL, 
#             json={'model': MODEL_NAME, 'prompt': prompt, 'stream': False, 'format': 'json'}, 
#             timeout=None  
#         )
#         reponse.raise_for_status()
        
#         raw_res = reponse.json()['response'].strip()
        
#         # Extraction robuste du bloc JSON situé entre { et }
#         match = re.search(r'\{.*\}', raw_res, re.DOTALL)
#         if match:
#             raw_res = match.group(0)
            
#         data = json.loads(raw_res)
#         tipo = str(data.get("type", "INCONNU")).strip().upper()
#         raison = str(data.get("raison", "Aucune explication fournie.")).strip()
        
#         duration = time.time() - start_time
#         logger.info(f"Classification IA en {duration:.2f}s : {tipo}")

#         metrics = {
#             "total_duration_seconds": duration,
#             "ollama_total_duration": reponse.json().get("total_duration"),
#             "load_duration": reponse.json().get("load_duration"),
#             "prompt_eval_count": reponse.json().get("prompt_eval_count"),
#             "eval_count": reponse.json().get("eval_count"),
#             "model": MODEL_NAME,
#             "confidence_score": res_json.get("confidence"),      # Métrique de certitude (1-5)
#             "extracted_keywords": res_json.get("keywords", []),  # Preuves textuelles
#             "detected_language": res_json.get("language", "fr"), # Langue du doc
#             "text_length_chars": len(texte_p1),
#             "text_word_count": len(texte_p1.split()),
#             # Détecte si le texte était tronqué ou trop court (indique un potentiel échec d'OCR)
#             "is_short_text": len(texte_p1.split()) < 20, 
#             # Analyse de confiance basée sur des mots-clés d'hésitation dans la raison
#             "has_uncertainty_keywords": any(w in raison.lower() for w in ["incertain", "doute", "hésite", "ambigu", "inconnu", "pas clair"]),
#             # Sauvegarde des tokens d'entrée/sortie pour l'analyse de volume
#             "prompt_tokens": reponse.json().get("prompt_eval_count"),
#             "generated_tokens": reponse.json().get("eval_count"),
#             "validation_status": "PENDING",  # Peut devenir "VALIDATED" ou "CORRECTED"
#             "is_correct": None,              # Sera True ou False après action humaine
#             "corrected_type": None           # Stockera le vrai type si l'IA s'est trompée
#         }
        
#         return tipo, raison, metrics

#     except json.JSONDecodeError:
#         logger.error("Le LLM n'a pas retourné un JSON valide.")
#         return "INCONNU", "Format de réponse invalide."
#     except Exception as e:
#         logger.error(f"Échec de l'appel Ollama : {str(e)}", exc_info=True)
#         return "INCONNU", f"Erreur système : {str(e)}"

# def classifier_page_pour_decoupage(texte_page: str) -> str:
#     if not texte_page.strip():
#         return "INCONNU"
        
#     prompt = f"Donne le type de ce contenu de page de marché public marocain parmi (RC, CPS, BORDEREAU_PRIX). Réponds juste le code, sinon réponds INCONNU : {texte_page[:800]}"
#     try:
#         reponse = requests.post(
#             OLLAMA_URL, 
#             json={'model': MODEL_NAME, 'prompt': prompt, 'stream': False}, 
#             timeout=15  
#         )
#         return reponse.json()['response'].strip().upper()
#     except Exception:
#         return "INCONNU"

def classifier_texte_document(texte: str, contexte_few_shot: str = "") -> tuple[str, str, dict]:
    """
    Analyse le texte et retourne un tuple : (TYPE_DETECTE, EXPLICATION, METRIQUES)
    """
    if not texte.strip():
        logger.warning("Texte vide reçu pour la classification globale.")
        return "INCONNU", "Le document ne contient aucun texte exploitable.", {}
    
    prompt = f"""{contexte_few_shot}

Analyse cet extrait de document de marché public au Maroc.
Détermine sa nature exacte parmi : AVIS_FRANCAIS, AVIS_ARABE, AVIS, RC, CPS, ACTE_ENGAGEMENT, DECLARATION_HONNEUR, BORDEREAU_PRIX, SCHEMA_TOPOLOGIQUE, AUTRE.

Tu dois répondre UNIQUEMENT sous la forme d'un objet JSON strict avec ces 5 clés exactes : 
- "type": Le code de la catégorie parmi la liste ci-dessus.
- "raison": Une phrase concise en français expliquant pourquoi.
- "confidence": Une note entière de 1 (très incertain) à 5 (certain à 100%).
- "keywords": Une liste de 3 ou 4 mots-clés décisifs trouvés dans le texte qui justifient ce choix.
- "language": Le code langue détecté ("fr", "ar").

Extrait :
{texte[:1500]}"""

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