import os, time, psutil, json
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import inspect, func, text
from backend.app.database.models import SystemMetric, TenderDocument, Tender, EmailNotification, ClassificationAuditLog, ScrapingStatus

# Capturer le timestamp de démarrage de l'application pour calculer l'uptime FastAPI
FASTAPI_START_TIME = time.time()

def collecter_et_sauvegarder_metriques(db: Session):
    """
    Scanne les composants hardware, le processus FastAPI, la base de données PostgreSQL,
    les logs d'inférence de l'IA et l'activité de scraping pour enregistrer un snapshot horaire.
    """
    current_process = psutil.Process(os.getpid())
    
    # ==========================================
    # 1. METRIQUES SERVER & HARDWARE
    # ==========================================
    uptime = int(time.time() - FASTAPI_START_TIME)
    
    # Métriques du processus FastAPI spécifique
    try:
        fastapi_mem = current_process.memory_info().rss / (1024 * 1024)  # En Mo
        fastapi_files = len(current_process.open_files()) + len(current_process.connections())
    except Exception:
        fastapi_mem = 0.0
        fastapi_files = 0
        
    vm = psutil.virtual_memory()

    hardware_health = {
        "cpu_usage_percent": psutil.cpu_percent(interval=None),
        "cpu_cores_logical": psutil.cpu_count(logical=True),
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        
        "ram_usage_percent": psutil.virtual_memory().percent,
        "ram_total_gb": round(vm.total / 1024**3,2),
        "ram_available_gb": round(vm.available / 1024**3,2),
        "ram_used_gb": round(vm.used / 1024**3,2),
        
        "disk_usage_percent": psutil.disk_usage('/').percent,
        "disk_total_gb": round(psutil.disk_usage("/").total/1024**3,2),
        "disk_free_gb": round(psutil.disk_usage("/").free/1024**3,2),

        "fastapi_uptime_seconds": uptime,
        "fastapi_memory_rss_mb": round(fastapi_mem, 2),
        "fastapi_open_files": fastapi_files
    }

    # ==========================================
    # 2. METRIQUES DATABASE (DYNAMIC SCAN)
    # ==========================================
    database_status = {
        "is_connected": False,
        "tables_count": 0,
        "database_size_mb": 0.0,
        "active_connections": 0,
        "largest_table": None,
        "largest_table_rows": 0,
        "last_backup": None,
        "rows_per_table": {}
    }

    try:
        inspector = inspect(db.bind)
        table_names = inspector.get_table_names()
        
        database_status["is_connected"] = True
        database_status["tables_count"] = len(table_names)
        
        # Taille totale de la base de données PostgreSQL
        try:
            db_size_bytes = db.execute(text("SELECT pg_database_size(current_database());")).scalar() or 0
            database_status["database_size_mb"] = round(db_size_bytes / (1024 * 1024), 2)
        except Exception:
            database_status["database_size_mb"] = 0.0

        # Connexions actives PostgreSQL
        try:
            active_conns = db.execute(text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active';")).scalar() or 0
            database_status["active_connections"] = active_conns
        except Exception:
            database_status["active_connections"] = 0
        
        rows_per_table = {}
        largest_table = None
        largest_rows = 0    
        for table in table_names:
            try:
                with db.begin_nested():
                    query = text(f'SELECT COUNT(*) FROM "{table}"')
                    result = db.execute(query).scalar()
                    rows_per_table[table] = result
                    if result > largest_rows:
                        largest_rows = result
                        largest_table = table
            except Exception as err:
                print(f"[METRICS WARN] Erreur lors du count sur la table '{table}': {err}")
                rows_per_table[table] = -1

        database_status["rows_per_table"] = rows_per_table
        database_status["largest_table"] = largest_table
        database_status["largest_table_rows"] = largest_rows
    except Exception as e:
        print(f"[METRICS ERROR] Échec de l'inspection de la BDD : {e}")

    # ==========================================
    # 3. METRIQUES SCRAPING
    # ==========================================
    # Récupération dynamique du nombre de documents scrapés aujourd'hui
    aujourd_hui = date.today()
    docs_scrapes_aujourd_hui = (
        db.query(TenderDocument)
        .join(Tender)
        .filter(func.date(Tender.created_at) == aujourd_hui)
        .count()
    )
    
    tenders_today = db.query(Tender).filter(func.date(Tender.created_at) == aujourd_hui)
    total_tenders_today_count = tenders_today.count()
    
    emails_received = db.query(func.count(EmailNotification.id)).filter(func.date(EmailNotification.received_at) == aujourd_hui).scalar() or 0
    emails_processed = db.query(func.count(EmailNotification.id)).filter(
        func.date(EmailNotification.received_at) == aujourd_hui, 
        EmailNotification.is_read == True
    ).scalar() or 0
    
    failed_scraping_count = (
        db.query(func.count(Tender.id))
        .filter(
            func.date(Tender.created_at) == aujourd_hui,
            Tender.scraping_status.in_([
                ScrapingStatus.SELENIUM_ERROR,
                ScrapingStatus.DOWNLOAD_ERROR
            ])
        )
        .scalar()
        or 0
    )

    success_rate_scraping = round(
        ((total_tenders_today_count - failed_scraping_count) / total_tenders_today_count * 100), 2
    ) if total_tenders_today_count > 0 else 100.0

    last_tender_created = db.query(func.max(Tender.created_at)).scalar()
    selenium_errors_total = db.query(func.count(Tender.id)).filter(
        Tender.scraping_status == "SELENIUM_ERROR" # Ou un LIKE sur le message d'erreur
    ).scalar() or 0
    # Vérifier si Chrome, Firefox ou le script du scraper tourne sur la machine
    scraper_running = any(
        p.info["name"] and (
            "chrome" in p.info["name"].lower() or
            "geckodriver" in p.info["name"].lower()
        )
        for p in psutil.process_iter(["name"])
    )
    
    last_tender = (
        db.query(Tender)
        .order_by(Tender.created_at.desc())
        .first()
    )

    last_sync_status = (
        last_tender.scraping_status.value
        if last_tender else None
    )

    # Note : Tu pourras lier ces valeurs à tes tables de logs ou d'états de tâches de scraping si tu en as
    scraping_metrics = {
        "total_scraped_today": docs_scrapes_aujourd_hui,
        "docs_downloaded_today": db.query(func.count(TenderDocument.id)).join(Tender).filter(func.date(Tender.created_at) == aujourd_hui).scalar() or 0,
        "zips_downloaded_today": tenders_today.filter(Tender.local_zip_path.isnot(None)).count(),
        "emails_received_today": emails_received,
        "emails_processed_today": emails_processed,
        "tenders_scraped_today": total_tenders_today_count,
        "avg_scraping_duration_sec": round(db.query(func.avg(Tender.scraping_duration_sec)).scalar() or 0.0, 2),
        "failed_scraping": failed_scraping_count,
        "success_rate": success_rate_scraping,
        "corrupted_zips_total": db.query(func.count(Tender.id)).filter(Tender.is_zip_corrupted == True).scalar() or 0,
        "selenium_errors_total": selenium_errors_total,  
        #"last_scraping": last_tender_created,
        "scraper_running": scraper_running,
        #"last_sync_timestamp": last_tender_created,
        "last_scraping": (
            last_tender_created.isoformat()
            if last_tender_created
            else None
        ),

        "last_sync_timestamp": (
            last_tender_created.isoformat()
            if last_tender_created
            else None
        ),
        "last_sync_status": last_sync_status,  # À dynamiser selon tes variables de statut
        #"active_scrapers": 0            # À incrémenter si un thread de scraping tourne
    }

    # ==========================================
    # 4. METRIQUES AI (INFERENCES OLLAMA / QWEN)
    # ==========================================
    # On filtre les métriques basées sur les documents traités la dernière heure
    # (En exploitant les temps de réponse déjà enregistrés dans tes documents)
    tous_docs_traites = db.query(TenderDocument).filter(TenderDocument.is_classified == True).all()
    
    # Simulation/Calcul basé sur tes colonnes de documents existantes
    # Note : Si tu as une table dédiée aux requêtes d'inférence, tu pourras cibler cette table à l'avenir.
    temps_reponses = [d.response_time for d in tous_docs_traites if d.response_time is not None]
    avg_time = sum(temps_reponses) / len(temps_reponses) if temps_reponses else 0.0
    
    # Inférences par fenêtre temporelle
    inf_today = db.query(func.count(ClassificationAuditLog.id)).filter(func.date(ClassificationAuditLog.created_at) == aujourd_hui).scalar() or 0
    inf_this_week = db.query(func.count(ClassificationAuditLog.id)).filter(ClassificationAuditLog.created_at >= (datetime.utcnow() - timedelta(days=7))).scalar() or 0
    inf_this_month = db.query(func.count(ClassificationAuditLog.id)).filter(ClassificationAuditLog.created_at >= (datetime.utcnow() - timedelta(days=30))).scalar() or 0
    
    # Répartition par Type prédit (RC, CPS, AVIS, AE, DH, BDP, AUTRE)
    types_breakdown = dict(db.query(ClassificationAuditLog.predicted_type, func.count(ClassificationAuditLog.id)).group_by(ClassificationAuditLog.predicted_type).all())

    # Statuts de validation (PENDING, VALIDATED, CORRECTED)
    validation_stats = dict(db.query(ClassificationAuditLog.validation_status, func.count(ClassificationAuditLog.id)).group_by(ClassificationAuditLog.validation_status).all())

    validated_count = validation_stats.get("VALIDATED", 0)
    corrected_count = validation_stats.get("CORRECTED", 0)
    total_reviewed = validated_count + corrected_count

    # Accuracy métier
    accuracy_ia = round((validated_count / total_reviewed * 100), 2) if total_reviewed > 0 else 100.0
    human_correction_rate = round((corrected_count / total_reviewed * 100), 2) if total_reviewed > 0 else 0.0
    error_rate = round(100 - accuracy_ia, 2)
    
    perf_stats = db.query(
        func.avg(ClassificationAuditLog.execution_duration_sec).label("avg_time"),
        func.min(ClassificationAuditLog.execution_duration_sec).label("min_time"),
        func.max(ClassificationAuditLog.execution_duration_sec).label("max_time"),
        func.stddev(ClassificationAuditLog.execution_duration_sec).label("stddev_time"),
        func.avg(ClassificationAuditLog.confidence_score).label("avg_confidence"),
        func.sum(ClassificationAuditLog.prompt_tokens).label("sum_p_tokens"),
        func.sum(ClassificationAuditLog.generated_tokens).label("sum_g_tokens"),
        func.avg(ClassificationAuditLog.ollama_total_duration).label("avg_ollama_time"),
        func.max(ClassificationAuditLog.ollama_total_duration).label("max_ollama")
    ).first()

    # Langues & Nature des Documents
    languages_breakdown = dict(db.query(ClassificationAuditLog.detected_language, func.count(ClassificationAuditLog.id)).group_by(ClassificationAuditLog.detected_language).all())

    total_inferences = db.query(func.count(ClassificationAuditLog.id)).scalar() or 0

    scanned_docs_count = db.query(func.count(ClassificationAuditLog.id)).filter(
        ClassificationAuditLog.is_scanned == True
    ).scalar() or 0

    native_text = total_inferences - scanned_docs_count    
    total_gen_tokens = perf_stats.sum_g_tokens or 0
    total_ollama_dur = perf_stats.avg_ollama_time or 1.0
    avg_prompt_size = db.query(
        func.avg(ClassificationAuditLog.text_length_chars)
    ).scalar() or 0

    ai_metrics = {
        "total_inferences_historical": len(tous_docs_traites),
        "average_response_time_sec": round(avg_time, 2),
        "error_rate_percent": error_rate,  
        "volumes": {
            "today": inf_today,
            "this_week": inf_this_week,
            "this_month": inf_this_month,
            "total_historical": db.query(func.count(ClassificationAuditLog.id)).scalar() or 0
        },
        "accuracy_and_quality": {
            "accuracy_ia_percent": accuracy_ia,
            "human_correction_rate_percent": human_correction_rate,
            "validation_status_breakdown": validation_stats, # {"PENDING": X, "VALIDATED": Y, "CORRECTED": Z}
            #"average_confidence": round(perf_stats.avg_confidence or 0.0, 2)
            "average_confidence": round(float(perf_stats.avg_confidence or 0.0), 2)
        },
        "performance_times_sec": {
            "avg": round(perf_stats.avg_time or 0.0, 2),
            "min": round(perf_stats.min_time or 0.0, 2),
            "max": round(perf_stats.max_time or 0.0, 2),
            "stddev": round(perf_stats.stddev_time or 0.0, 2),
            "avg_ollama_duration": round(perf_stats.avg_ollama_time or 0.0, 2)
        },
        "tokens_and_llm": {
            "total_prompt_tokens": perf_stats.sum_p_tokens or 0,
            "total_generated_tokens": total_gen_tokens,
            "tokens_per_second": round(total_gen_tokens / total_ollama_dur, 2) if total_ollama_dur > 0 else 0.0,
            "avg_prompt_size_chars": round(float(avg_prompt_size), 0)
        },
        "breakdowns": {
            "document_types": types_breakdown,       # {"RC": 12, "CPS": 45, "AVIS": 8...}
            "languages": languages_breakdown,         # {"FR": 100, "AR": 20, "MIXED": 5}
            "scanned_vs_text": {
                "scanned_ocr": scanned_docs_count,
                "native_text": native_text
            }
        }
    }
    
    total_classifications = db.query(func.count(ClassificationAuditLog.id)).scalar() or 0
    
    avg_ollama = round(perf_stats.avg_ollama_time or 0.0, 2)
    min_pipeline = round(perf_stats.min_time or 0.0, 2)
    max_pipeline = round(perf_stats.max_time or 0.0, 2)
    avg_pipeline = round(perf_stats.avg_time or 0.0, 2)
    avg_confidence = round(float(perf_stats.avg_confidence or 0.0), 2)
    
    # Pourcentage d'OCR et documents mixtes
    ocr_percent = round((scanned_docs_count / total_classifications * 100), 2) if total_classifications > 0 else 0.0
    docs_mixtes_count = db.query(func.count(ClassificationAuditLog.id)).filter(
        ClassificationAuditLog.detected_language == "MIXED"
    ).scalar() or 0
    
    # Mappings direct des breakdowns
    langues = languages_breakdown
    types_detectes = types_breakdown
    
    # Tokens & Débits
    total_prompt_tokens = perf_stats.sum_p_tokens or 0
    total_tokens = total_prompt_tokens + total_gen_tokens
    tokens_per_sec = round(total_gen_tokens / total_ollama_dur, 2) if total_ollama_dur > 0 else 0.0
    time_per_token_ms = round((total_ollama_dur * 1000) / total_gen_tokens, 2) if total_gen_tokens > 0 else 0.0

    # Statistiques avancées sur les documents PDF/Fichiers
    doc_stats = db.query(
        func.avg(TenderDocument.page_count).label("avg_pages"),
        func.avg(TenderDocument.file_size_mb).label("avg_size_mb"),
        func.avg(TenderDocument.word_count).label("avg_words"),
        func.max(TenderDocument.file_size_mb).label("max_size_mb"),
        func.max(TenderDocument.ocr_duration_sec).label("max_ocr_duration")
    ).first()

    # Statuts de validation
    validated = validation_stats.get("VALIDATED", 0)
    corrected = validation_stats.get("CORRECTED", 0)
    pending = validation_stats.get("PENDING", 0)
    taux_correction = human_correction_rate

    # Historique journalier des 7 derniers jours
    sept_jours_avant = date.today() - timedelta(days=7)
    historique_journalier_query = db.query(
        func.date(ClassificationAuditLog.created_at).label("jour"),
        func.count(ClassificationAuditLog.id).label("total")
    ).filter(
        ClassificationAuditLog.created_at >= sept_jours_avant
    ).group_by(
        func.date(ClassificationAuditLog.created_at)
    ).all()
    
    historique_journalier = {str(r.jour): r.total for r in historique_journalier_query}
    
    ai_pipeline_metrics = {
        "total_classifications": total_classifications,
        "temps_moyen": avg_ollama,              # Temps moyen du LLM
        "temps_mini": min_pipeline,
        "temps_maxi": max_pipeline,
        "confidence_moyenne": avg_confidence,
        "accuracy_ia": accuracy_ia,
        "ocr_percent": ocr_percent,
        "documents_mixtes": docs_mixtes_count,
        "langues": langues,
        "types_detectes": types_detectes,
        "tokens": {
            "prompt": total_prompt_tokens,
            "generated": total_gen_tokens,
            "total": total_tokens
        },
        "tokens_sec": tokens_per_sec,
        "temps_par_token_ms": time_per_token_ms,
        "pipeline_moyen": avg_pipeline,          # Durée totale du pipeline complet
            
        "documents_stats": {
            "pages_moyennes": round(float(doc_stats.avg_pages or 0.0), 1),
            "taille_moyenne_mb": round(float(doc_stats.avg_size_mb or 0.0), 2),
            "mots_moyens": round(float(doc_stats.avg_words or 0), 0),
            "plus_gros_document_mb": round(float(doc_stats.max_size_mb or 0.0), 2),
            "plus_long_ocr_sec": round(float(doc_stats.max_ocr_duration or 0.0), 2),
            "plus_long_llm_sec": round(float(perf_stats.max_ollama or 0.0), 2)
        },
            
        "validation": {
            "VALIDATED": validated,
            "CORRECTED": corrected,
            "PENDING": pending,
            "accuracy": accuracy_ia,
            "taux_de_correction": taux_correction
        },
            
        "volumes_historique": {
            "historique_journalier": historique_journalier
        }
    }

    # ==========================================
    # 5. ENREGISTREMENT EN BASE DE DONNÉES
    # ==========================================
    nouvelle_metrique = SystemMetric(
        server_and_hardware_health=hardware_health,
        database_status=database_status,
        scraping_metrics=scraping_metrics,
        ai_metrics=ai_metrics,
        ai_and_pipeline = ai_pipeline_metrics
    )
    
    try:
        db.add(nouvelle_metrique)
        def verifier_json(obj, chemin="root"):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    verifier_json(v, f"{chemin}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    verifier_json(v, f"{chemin}[{i}]")
            elif isinstance(obj, (datetime, date)):
                print(f"❌ Date trouvée : {chemin} -> {obj}")
            else:
                try:
                    json.dumps(obj)
                except TypeError:
                    print(f"❌ Type non sérialisable : {chemin} -> {type(obj)}")
        verifier_json(hardware_health, "hardware_health")
        verifier_json(database_status, "database_status")
        verifier_json(scraping_metrics, "scraping_metrics")
        verifier_json(ai_metrics, "ai_metrics")
        verifier_json(ai_pipeline_metrics, "ai_pipeline_metrics")
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[METRICS ERROR] Impossible d'insérer les métriques en BDD : {e}")