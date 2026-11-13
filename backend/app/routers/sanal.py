"""Sanal portföy (hayali para, kullanıcıya özel, giriş gerekir) ve "Ya o zaman alsaydım?" (herkese açık).
Mantık: app/services/sanal_portfoy.py"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user
from app.models import User
from app.schemas import SanalOrderIn, SanalOut, SanalResetIn, WhatIfOut
from app.services import sanal_portfoy as S

router = APIRouter(prefix="/sanal-portfoy", tags=["sanal-portfoy"])


def _run(fn, *args):
    try:
        return fn(*args)
    except S.SanalHata as e:
        raise HTTPException(400, str(e)) from e


@router.get("", response_model=SanalOut)
def get_portfolio(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return S.summary(db, user.id)


@router.post("/emir", response_model=SanalOut)
def post_order(body: SanalOrderIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.side == S.ALIS:
        _run(S.place_buy, db, user.id, body.code, body.amount)
    else:
        _run(S.place_sell, db, user.id, body.code, body.units)
    return S.summary(db, user.id)


@router.delete("/emir/{order_id}", response_model=SanalOut)
def delete_order(order_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        S.cancel(db, user.id, order_id)
    except S.SanalHata as e:
        raise HTTPException(404 if "bulunamadı" in str(e) else 400, str(e)) from e
    return S.summary(db, user.id)


@router.post("/sifirla", response_model=SanalOut)
def post_reset(body: SanalResetIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _run(S.reset, db, user.id, body.initial_balance)
    return S.summary(db, user.id)


@router.get("/geriye", response_model=WhatIfOut)
def get_what_if(
    funds: str = Query(..., description="Virgülle ayrılmış fon kodları (en fazla 4)"),
    tarih: date = Query(..., description="Alış tarihi; o gün işlem yoksa sonraki ilk işlem günü"),
    tutar: float = Query(10_000, gt=0, le=S.MAX_BALANCE),
    db: Session = Depends(get_db),
):
    return _run(S.what_if, db, funds.split(","), tarih, tutar)
