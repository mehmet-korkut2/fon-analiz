from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import fx

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("")
def get_fx(source: Literal["canli", "tcmb"] = "canli", db: Session = Depends(get_db)):
    """Döviz, altın ve diğer piyasa fiyatları.

    - **canli**: birkaç dakikada bir güncellenen fiyatlar (önbellek 60 sn)
    - **tcmb**: TCMB resmi gösterge kurları (günde bir kez)

    Kaynağa ulaşılamazsa son bilinen kurlar `stale: true` ve `fetched_at` ile döner.
    """
    try:
        return fx.get_rates(source, db=db)
    except fx.FxError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
