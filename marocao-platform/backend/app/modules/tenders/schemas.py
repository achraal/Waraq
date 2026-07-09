from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class TenderFilter(BaseModel):
    deadline: Optional[str] = None # Accepte "2026", "2026-07", "2026-07-02"
    extraction_date: Optional[str] = None # Accepte tout format de date lisible
    is_consulted: Optional[bool] = None
    category: Optional[str] = None

class TenderDelete(BaseModel):
    ids: List[str]