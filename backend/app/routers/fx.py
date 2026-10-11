from typing import Literal

from fastapi import APIRouter, HTTPException

from app.services import fx

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("")
def get_fx(source: Literal["canli", "tcmb"] = "canli"):
    """Döviz, altın ve diğer piyasa fiyatları.

    - **canli**: birkaç dakikada bir güncellenen fiyatlar (önbellek 60 sn)
    - **tcmb**: TCMB resmi gösterge kurları (günde bir kez)
    """
    try:
        return fx.get_rates(source)
    except fx.FxError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
