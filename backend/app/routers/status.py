import threading

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import scheduler
from app.database import get_db
from app.models import Fund, Price
from app.services import updater

router = APIRouter(prefix="/status", tags=["status"])


@router.get("")
def get_status(db: Session = Depends(get_db)):
    """Veritabanının ve günlük güncellemenin durumu."""
    last = updater.last_result
    return {
        "fund_count": db.scalar(select(func.count()).select_from(Fund)),
        "price_count": db.scalar(select(func.count()).select_from(Price)),
        "latest_price_date": db.scalar(select(func.max(Price.date))),
        "next_update": scheduler.next_run(),
        "last_update": last.to_dict() if last else None,
    }


@router.post("/update")
def trigger_update(limit: int = 0):
    """Güncellemeyi hemen arka planda başlatır (geliştirme ve test için)."""
    if updater._lock.locked():
        return {"started": False, "message": "Bir güncelleme zaten çalışıyor."}
    threading.Thread(target=updater.run_update, kwargs={"months": 1, "limit": limit}, daemon=True).start()
    return {"started": True, "message": "Güncelleme başladı. Durumu GET /api/status ile izle."}
