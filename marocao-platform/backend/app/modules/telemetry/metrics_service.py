import os, time, psutil
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import inspect, func, text
from backend.app.database.models import SystemMetric, TenderDocument, Tender

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

    hardware_health = {
        "cpu_usage_percent": psutil.cpu_percent(interval=None),
        "ram_usage_percent": psutil.virtual_memory().percent,
        "disk_usage_percent": psutil.disk_usage('/').percent,
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
        "rows_per_table": {}
    }

    try:
        inspector = inspect(db.bind)
        table_names = inspector.get_table_names()
        
        database_status["is_connected"] = True
        database_status["tables_count"] = len(table_names)
        
        rows_per_table = {}
        for table in table_names:
            try:
                with db.begin_nested():
                    query = text(f'SELECT COUNT(*) FROM "{table}"')
                    result = db.execute(query).scalar()
                    rows_per_table[table] = result
            except Exception as err:
                print(f"[METRICS WARN] Erreur lors du count sur la table '{table}': {err}")
                rows_per_table[table] = -1

        database_status["rows_per_table"] = rows_per_table
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

    # Note : Tu pourras lier ces valeurs à tes tables de logs ou d'états de tâches de scraping si tu en as
    scraping_metrics = {
        "total_scraped_today": docs_scrapes_aujourd_hui,
        "last_sync_status": "SUCCESS",  # À dynamiser selon tes variables de statut
        "active_scrapers": 0            # À incrémenter si un thread de scraping tourne
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

    ai_metrics = {
        "total_inferences_historical": len(tous_docs_traites),
        "average_response_time_sec": round(avg_time, 2),
        "error_rate_percent": 0.0  # Calculable en comptant les 'INCONNU' dans tes types
    }

    # ==========================================
    # 5. ENREGISTREMENT EN BASE DE DONNÉES
    # ==========================================
    nouvelle_metrique = SystemMetric(
        server_and_hardware_health=hardware_health,
        database_status=database_status,
        scraping_metrics=scraping_metrics,
        ai_metrics=ai_metrics
    )
    
    try:
        db.add(nouvelle_metrique)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[METRICS ERROR] Impossible d'insérer les métriques en BDD : {e}")