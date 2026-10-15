"""Sanal portföy (hayali para, tek kullanıcı) ve "Ya o zaman alsaydım?". Mantık: app/services/sanal_portfoy.py"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SanalOrderIn, SanalOut, SanalResetIn, WhatIfOut
from app.services import sanal_portfoy as S

router = APIRouter(prefix="/sanal-portfoy", tags=["sanal-portfoy"])


def _run(fn, *args):
    try:
        return fn(*args)
    except S.SanalHata as e:
        raise HTTPException(400, str(e)) from e


@router.get("", response_model=SanalOut)
def get_portfolio(db: Session = Depends(get_db)):
    return S.summary(db)


@router.post("/emir", response_model=SanalOut)
def post_order(body: SanalOrderIn, db: Session = Depends(get_db)):
    if body.side == S.ALIS:
        _run(S.place_buy, db, body.code, body.amount)
    else:
        _run(S.place_sell, db, body.code, body.units)
    return S.summary(db)


@router.delete("/emir/{order_id}", response_model=SanalOut)
def delete_order(order_id: int, db: Session = Depends(get_db)):
    _run(S.cancel, db, order_id)
    return S.summary(db)


@router.post("/sifirla", response_model=SanalOut)
def post_reset(body: SanalResetIn, db: Session = Depends(get_db)):
    _run(S.reset, db, body.initial_balance)
    return S.summary(db)


@router.get("/geriye", response_model=WhatIfOut)
def get_what_if(
    funds: str = Query(..., description="Virgülle ayrılmış fon kodları (en fazla 4)"),
    tarih: date = Query(..., description="Alış tarihi; o gün işlem yoksa sonraki ilk işlem günü"),
    tutar: float = Query(10_000, gt=0, le=S.MAX_BALANCE),
    db: Session = Depends(get_db),
):
    return _run(S.what_if, db, funds.split(","), tarih, tutar)
