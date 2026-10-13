from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Fund, Price
from app.routers.funds import fund_out, stale_cutoff
from app.schemas import CompareFund, CompareOut, ComparePoint

router = APIRouter(prefix="/compare", tags=["compare"])

MIN_FUNDS, MAX_FUNDS = 2, 4
BASE_LOOKBACK_DAYS = 10  # dönem başı tatile denk gelirse önceki son fiyatı bulmak için


@router.get("", response_model=CompareOut)
def compare(
    funds: str = Query(..., description="Virgülle ayrılmış 2-4 fon kodu, ör. TTE,AFA"),
    months: int = Query(12, ge=1, le=60, description="Kaç aylık geçmiş (start verilmezse)"),
    start: date | None = Query(None, description="Baz tarih (bu gün ya da önceki son fiyat 100 olur); YBB için önceki yılın 31 Aralık'ı"),
    db: Session = Depends(get_db),
):
    codes = list(dict.fromkeys(c.strip().upper() for c in funds.split(",") if c.strip()))
    if not MIN_FUNDS <= len(codes) <= MAX_FUNDS:
        raise HTTPException(422, f"{MIN_FUNDS} ile {MAX_FUNDS} arasında farklı fon seçmelisin.")

    found = {f.code: f for f in db.scalars(select(Fund).where(Fund.code.in_(codes)).options(joinedload(Fund.metrics)))}
    missing = [c for c in codes if c not in found]
    if missing:
        raise HTTPException(404, f"Bulunamayan fon: {', '.join(missing)}")

    latest = db.scalar(select(func.max(Price.date)).where(Price.fund_code.in_(codes)))
    if latest is None:
        raise HTTPException(422, "Seçilen fonların fiyat verisi yok.")
    # Dönem başı metriklerle aynı tanım (DateOffset), böylece getiriler metrik kartlarıyla tutarlı
    since = start or (pd.Timestamp(latest) - pd.DateOffset(months=months)).date()
    rows = db.execute(
        select(Price.date, Price.fund_code, Price.price)
        .where(Price.fund_code.in_(codes), Price.date >= since - timedelta(days=BASE_LOOKBACK_DAYS))
    ).all()
    df = pd.DataFrame(rows, columns=["date", "code", "price"]).pivot(index="date", columns="code", values="price")
    df = df.reindex(columns=[c for c in codes if c in df.columns]).sort_index()
    no_data = [c for c in codes if c not in df.columns]
    if no_data:
        raise HTTPException(422, f"Bu dönemde fiyat verisi olmayan fon: {', '.join(no_data)}")

    # Tatil farkları için boşlukları önceki fiyatla doldur; ama fonun son fiyatından sonrasını
    # doldurma (verisi kesilen fon düz çizgiyle devam ediyormuş gibi görünmesin)
    last_valid = {c: df[c].last_valid_index() for c in df.columns}
    df = df.ffill()
    for c, d in last_valid.items():
        df.loc[df.index > d, c] = None

    # Baz gün: dönem başındaki (ya da öncesindeki son) ortak gün; metriklerdeki getiri tanımıyla aynı.
    # Fonlardan biri o tarihte yoksa (yeni fon) hepsinin verisi olan ilk gün.
    complete = df.dropna()
    if complete.empty:
        raise HTTPException(422, "Seçilen fonların bu dönemde ortak fiyat verisi yok.")
    before = complete.index[complete.index <= since]
    base = before[-1] if len(before) else complete.index[0]

    norm = df.loc[base:] / df.loc[base] * 100
    cutoff = stale_cutoff(db)
    out_funds = []
    for c in codes:
        s = norm[c].dropna()
        out = CompareFund(**fund_out(found[c], cutoff).model_dump())
        out.period_return = s.iloc[-1] / 100 - 1 if len(s) else None
        out_funds.append(out)

    points = [
        ComparePoint(date=d, values={c: (None if pd.isna(v) else round(float(v), 4)) for c, v in row.items()})
        for d, row in norm.iterrows()
    ]
    return CompareOut(funds=out_funds, base_date=base, points=points)
