"""Enflasyon (TÜFE) durumu ve ana sayfa özeti. Mantık: app/services/inflation.py"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import inflation as I

router = APIRouter(prefix="/inflation", tags=["inflation"])


@router.get("")
def inflation_status(db: Session = Depends(get_db)):
    """TÜFE verisinin durumu (anahtarın değeri değil, yalnızca tanımlı olup olmadığı) ve son 12 ayda enflasyonu yenen
    fonların payı. Pay, dönem başında fiyatı olan her fonu kapsar (dönem içinde kapananlar dahil); yalnızca bugün
    aktif olan fonlarla hesaplanan pay karşılaştırma için ayrıca verilir."""
    return {**I.status(db), "summary": I.beat_summary_cached(db)}
