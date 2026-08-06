import logging, requests, time, json, re, torch, pypdf, fitz
from typing import Optional
from backend.app.config import settings
from backend.app.modules.ai_processor.ocr_engine import extraire_texte_page_pdf_avec_meta

logger = logging.getLogger("app.ai_processor.llm_analyzer")

OLLAMA_URL = f"{settings.OLLAMA_BASE_URL}/api/generate"
MODEL_NAME = settings.OLLAMA_MODEL

# ==========================================
# 1. UTILITAIRES HARDWARE & LECTURE PDF
# ==========================================

def construire_metriques(
    model: str = MODEL_NAME,
    confidence: Optional[int] = None,
    keywords: list = None,
    language: str = "fr",
    duration: float = 0.0,
    texte: str = "",
    is_scanned: bool = False,
    inspection_method: str = "NATIVE_TEXT_PYMUPDF",
    data_json: dict = None,
    reponse_ollama: dict = None,
    raison: str = "",
    validation_status: str = "PENDING",
    extra_metrics: dict = None,
    page_count=None,
    word_count=None,
    file_size_mb=None,
    ocr_duration_sec=None,
) -> dict:
    """Helper unique et universel pour garantir une structure de métriques 100% identique dans toute l'application."""
    reponse_ollama = reponse_ollama or {}
    extra_metrics = extra_metrics or {}
    data_json = data_json or {}
    mots = texte.split() if texte else []
    
    # Priorité aux métriques extraites du JSON / Ollama
    duration_val = extra_metrics.get("execution_duration_sec", duration)
    confidence_val = extra_metrics.get("confidence_score", confidence)
    keywords_val = extra_metrics.get("extracted_keywords", keywords or [])
    language_val = extra_metrics.get("detected_language", language)

    base_metadata = {
        "model": model,
        "confidence_score": confidence_val,
        "extracted_keywords": keywords_val,
        "detected_language": language_val,
        "execution_duration_sec": duration_val,
        "text_length_chars": len(texte),
        "text_word_count": len(mots),
        "page_count": page_count,
        "word_count": word_count,
        "file_size_mb": file_size_mb,
        "ocr_duration_sec": ocr_duration_sec,
        "is_short_text": len(mots) < 20 if mots else True,
        "has_uncertainty_keywords": any(w in raison.lower() for w in ["incertain", "doute", "hésite", "ambigu", "inconnu", "pas clair"]),
        "ollama_total_duration": reponse_ollama.get("total_duration") or extra_metrics.get("ollama_total_duration"),
        "load_duration": reponse_ollama.get("load_duration") or extra_metrics.get("load_duration"),
        "prompt_tokens": reponse_ollama.get("prompt_eval_count") or extra_metrics.get("prompt_tokens") or data_json.get("prompt_eval_count"),
        "generated_tokens": reponse_ollama.get("eval_count") or extra_metrics.get("generated_tokens") or data_json.get("eval_count"),
        "is_scanned": is_scanned,
        "inspection_method": inspection_method,
        "validation_status": validation_status,
        "is_correct": None,
        "corrected_type": None
    }

    # Fusion propre de champs supplémentaires éventuels
    for k, v in extra_metrics.items():
        if k not in base_metadata:
            base_metadata[k] = v

    logger.info(
        "[BUILD METRICS] pages=%s | words=%s | size=%s | ocr=%s",
        page_count,
        word_count,
        file_size_mb,
        ocr_duration_sec,
    )

    return base_metadata

    logger.info(
        "[BUILD RESULT] %s",
        {
            "page_count": base_metadata["page_count"],
            "word_count": base_metadata["word_count"],
            "file_size_mb": base_metadata["file_size_mb"],
            "ocr_duration_sec": base_metadata["ocr_duration_sec"],
        }
    )

def obtenir_device_execution() -> str:
    """Vérifie la disponibilité d'un GPU CUDA."""
    if torch.cuda.is_available():
        device = "cuda"
        logger.info(f"GPU détecté : {torch.cuda.get_device_name(0)} - Exécution sur GPU.")
    else:
        device = "cpu"
        logger.info("Aucun GPU détecté - Bascule sur CPU.")
    return device
    
DEVICE = obtenir_device_execution()
   
def extraire_texte_par_lots(path_pdf: str, taille_lot: int = 10) -> list[dict]:
    """Lit un PDF par paquets de `taille_lot` pages."""
    lots_texte = []
    doc = None
    try:
        doc = fitz.open(path_pdf)
        total_pages = len(doc)

        for i in range(0, total_pages, taille_lot):
            contient_scan = False
            texte_lot = ""
            derniere_methode = "NATIVE_TEXT_PYMUPDF"

            for idx_page in range(i, min(i + taille_lot, total_pages)):
                #res_meta = extraire_texte_page_pdf_avec_meta(doc, page_num=idx_page)
                res_meta = extraire_texte_page_pdf_avec_meta(doc, page_num=idx_page, path_pdf=path_pdf)
                
                txt = res_meta.get("text", "")
                texte_lot += f"\n--- Page {idx_page + 1} ---\n" + txt

                if res_meta.get("is_scanned", False):
                    contient_scan = True
                    derniere_methode = res_meta.get("inspection_method", "FAST_OCR_ONNX_HEADER")

            lots_texte.append({
                "lot_index": (i // taille_lot) + 1,
                "page_debut": i + 1,
                "page_fin": min(i + taille_lot, total_pages),
                "texte": texte_lot,
                "is_scanned": contient_scan,
                "inspection_method": derniere_methode
            })
            
    except Exception as e:
        logger.error(f"Échec de la lecture du PDF {path_pdf}: {e}")
    finally:
        # Garantit que le fichier est toujours fermé proprement, même en cas d'erreur
        if doc:
            doc.close()

    return lots_texte

# ==========================================
# 2. CLASSIFICATION LLM (OLLAMA)
# ==========================================
def verifier_ou_classifier_par_llm(
    texte: str, 
    type_primitif_detecte: str = None, 
    contexte_few_shot: str = "",
    is_scanned: bool = False,
    inspection_method: str = "NATIVE_TEXT_PYMUPDF",
    page_count=None,
    word_count=None,
    file_size_mb=None,
    ocr_duration_sec=None,
    ) -> dict:
    """
    Vérifie si le type primitif détecté est valide via le LLM.
    Si aucun type primitif n'est fourni, lance une classification complète.
    """
    logger.info(
        "[LLM INPUT] pages=%s | words=%s | size=%s | ocr=%s",
        page_count,
        word_count,
        file_size_mb,
        ocr_duration_sec,
    )
    if not type_primitif_detecte or type_primitif_detecte == "INCONNU":
        tipo, raison, metrics = classifier_texte_document(
            texte, 
            contexte_few_shot,
            is_scanned=is_scanned, 
            inspection_method=inspection_method,
            page_count=page_count,
            word_count=word_count,
            file_size_mb=file_size_mb,
            ocr_duration_sec=ocr_duration_sec,
        )
        return {
            "est_valide": tipo != "INCONNU",
            "type_confirme": tipo,
            "justification": raison,
            "langue": metrics.get("detected_language", "fr"),
            "metrics": metrics
        }

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
    start_time = time.time()
    try:
        reponse = requests.post(
            OLLAMA_URL,
            json={'model': MODEL_NAME, 'prompt': prompt, 'stream': False, 'format': 'json'},
            timeout=None
        )
        reponse.raise_for_status()
        reponse_json_data = reponse.json()
        raw_res = reponse_json_data.get('response', '').strip()
        
        match = re.search(r'\{.*\}', raw_res, re.DOTALL)
        if match:
            raw_res = match.group(0)

        data = json.loads(raw_res)
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', texte))
        latin_chars = len(re.findall(r'[A-Za-zÀ-ÿ]', texte))

        langue = str(data.get("langue", "fr")).lower()

        if arabic_chars > latin_chars:
            langue = "ar"

        data["langue"] = langue
        duration = time.time() - start_time
                
        return {
            "est_valide": bool(data.get("est_valide", False)),
            "type_confirme": str(data.get("type_confirme", type_primitif_detecte)).strip().upper(),
            "justification": str(data.get("justification", "Validation primitive.")),
            #"langue": str(data.get("langue", "fr")).lower(),
            "langue": langue,
            "metrics": construire_metriques(
                is_scanned=is_scanned,
                inspection_method=inspection_method,
                texte=texte,
                duration=duration,
                data_json=data,
                reponse_ollama=reponse_json_data,
                raison=str(data.get("justification", "")),
                validation_status="PENDING",
                page_count=page_count,
                word_count=word_count,
                file_size_mb=file_size_mb,
                ocr_duration_sec=ocr_duration_sec,
            )
        }
    except Exception as e:
        logger.error(f"Échec lors de la vérification LLM de la primitive : {e}")
        return {
            "est_valide": False,
            "type_confirme": "INCONNU",
            "justification": f"Erreur de validation LLM : {str(e)}",
            "langue": "fr",
            "metrics": construire_metriques(
                is_scanned=is_scanned,
                inspection_method=inspection_method,
                texte=texte,
                duration=time.time() - start_time if 'start_time' in locals() else 0.0,
                validation_status="FAILED",
                page_count=page_count,
                word_count=word_count,
                file_size_mb=file_size_mb,
                ocr_duration_sec=ocr_duration_sec,
            )
        }

def classifier_texte_document(
    texte: str, 
    contexte_few_shot: str = "", 
    is_scanned: bool = False, 
    inspection_method: str = "NATIVE_TEXT_PYMUPDF",
    page_count=None,
    word_count=None,
    file_size_mb=None,
    ocr_duration_sec=None,
    ) -> tuple[str, str, dict]:
    """Analyse le texte via Ollama et retourne : (TYPE_DETECTE, EXPLICATION, METRIQUES)"""
    logger.info(
        "[CLASSIFIER INPUT] pages=%s | words=%s | size=%s | ocr=%s",
        page_count,
        word_count,
        file_size_mb,
        ocr_duration_sec,
    )
    if not texte.strip():
        logger.warning("Texte vide reçu pour la classification.")
        return "INCONNU", "Le document ne contient aucun texte exploitable.", construire_metriques(
            is_scanned=is_scanned,
            inspection_method=inspection_method,
            texte="",
            validation_status="FAILED",
            page_count=page_count,
            word_count=word_count,
            file_size_mb=file_size_mb,
            ocr_duration_sec=ocr_duration_sec,
        )

    if texte.startswith("FICHIER_TECHNIQUE_DAO_"):
        ext_type = texte.split("_")[-1]
        return "SCHEMA_TOPOLOGIQUE", f"Fichier de dessin technique CAO/DAO ({ext_type}).", construire_metriques(
            is_scanned=is_scanned,
            inspection_method=inspection_method,
            texte=texte,
            validation_status="PENDING",
            page_count=page_count,
            word_count=word_count,
            file_size_mb=file_size_mb,
            ocr_duration_sec=ocr_duration_sec,
        )

    if len(texte) > 3500:
        extrait_analyse = f"{texte[:2000]}\n\n[... CONTENU INTERMÉDIAIRE SERPENTÉ ...]\n\n{texte[-1500:]}"
    else:
        extrait_analyse = texte
        
    # Détection de langue avant le LLM
    import re

    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', texte))
    latin_chars = len(re.findall(r'[A-Za-zÀ-ÿ]', texte))

    if arabic_chars > latin_chars:
        langue_forcee = "ar"
    else:
        langue_forcee = None

    prompt = f"""{contexte_few_shot}

Tu analyses un document provenant d'un dossier de marché public marocain.

OBJECTIF :
Détermine si ce document correspond réellement à l'une des pièces officielles suivantes :

- AVIS_FRANCAIS
- AVIS_ARABE
- AVIS
- RC
- CPS
- ACTE_ENGAGEMENT
- DECLARATION_HONNEUR
- BORDEREAU_PRIX
- SCHEMA_TOPOLOGIQUE
- DECOUPAGE_PDF_AUTOMATIQUE

IMPORTANT :

Si le document est en réalité un autre type de document (par exemple : rapport d'essais, rapport géotechnique, rapport de laboratoire, étude technique, note de calcul, plan, mémoire technique, fiche technique, PV, facture, courrier, certificat, etc.), tu DOIS répondre "AUTRE".

Ne cherche jamais à rapprocher artificiellement un document technique d'un AVIS, RC ou CPS simplement parce qu'il contient les mots "marché", "appel d'offres", "maître d'ouvrage" ou "ONEE".

Si plusieurs documents distincts sont assemblés dans un même PDF (exemple : RC suivi d'un CPS ou d'un Bordereau), retourne "DECOUPAGE_PDF_AUTOMATIQUE".

Réponds UNIQUEMENT avec un objet JSON valide contenant exactement ces clés :

- "type" : catégorie retenue.
- "raison" : explique précisément pourquoi ce choix. Si le type est AUTRE, indique clairement la nature réelle du document (exemple : "Rapport d'essais géotechniques du laboratoire Test Building", "Étude hydraulique", "Mémoire technique de l'entreprise", etc.).
- "confidence" : entier de 1 à 5.
- "keywords" : 3 ou 4 mots-clés justifiant la décision.
- "language" : "fr" ou "ar".

Document :
{extrait_analyse}
"""    

    logger.info(f"Envoi de la requête de classification à Ollama ({MODEL_NAME})...")
    start_time = time.time()
    try:
        reponse = requests.post(
            OLLAMA_URL,
            json={'model': MODEL_NAME, 'prompt': prompt, 'stream': False, 'format': 'json'},
            timeout=None
        )
        reponse.raise_for_status()

        reponse_json_data = reponse.json()
        raw_res = reponse_json_data.get('response', '').strip()

        match = re.search(r'\{.*\}', raw_res, re.DOTALL)
        if match:
            raw_res = match.group(0)

        data = json.loads(raw_res)
        language_val = data.get("language", "fr").lower()

        if langue_forcee:
            language_val = langue_forcee

        data["language"] = language_val
        tipo = str(data.get("type", "INCONNU")).strip().upper()
        raison = str(data.get("raison", "Aucune explication fournie.")).strip()

        duration = time.time() - start_time
        logger.info(f"Classification IA en {duration:.2f}s : {tipo}")
        confidence_val = data.get("confidence", None)

        metrics = construire_metriques(
            is_scanned=is_scanned,
            inspection_method=inspection_method,
            texte=texte,
            confidence=confidence_val,
            duration=duration,
            data_json=data,
            reponse_ollama=reponse_json_data,
            raison=raison,
            validation_status="PENDING",
            page_count=page_count,
            word_count=word_count,
            file_size_mb=file_size_mb,
            ocr_duration_sec=ocr_duration_sec,
        )

        logger.info(
            "[CLASSIFIER OUTPUT] %s",
            {
                "page_count": metrics.get("page_count"),
                "word_count": metrics.get("word_count"),
                "file_size_mb": metrics.get("file_size_mb"),
                "ocr_duration_sec": metrics.get("ocr_duration_sec"),
            }
        )

        return tipo, raison, metrics

    except json.JSONDecodeError:
        logger.error("Le LLM n'a pas retourné un JSON valide.")
        return "INCONNU", "Format de réponse invalide.", construire_metriques(
            is_scanned=is_scanned,
            inspection_method=inspection_method,
            texte=texte,
            duration=time.time() - start_time if 'start_time' in locals() else 0.0,
            validation_status="FAILED",
            page_count=page_count,
            word_count=word_count,
            file_size_mb=file_size_mb,
            ocr_duration_sec=ocr_duration_sec,
        )
    except Exception as e:
        logger.error(f"Échec de l'appel Ollama : {str(e)}", exc_info=True)
        return "INCONNU", f"Erreur système : {str(e)}", construire_metriques(
            is_scanned=is_scanned,
            inspection_method=inspection_method,
            texte=texte,
            duration=time.time() - start_time if 'start_time' in locals() else 0.0,
            validation_status="FAILED",
            page_count=page_count,
            word_count=word_count,
            file_size_mb=file_size_mb,
            ocr_duration_sec=ocr_duration_sec,
        )