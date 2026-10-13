"""Tüm fonların metriklerini hesaplayıp fund_metrics tablosuna yazar."""
from __future__ import annotations

import logging
import statistics
import time
from dataclasses import asdict
from datetime import timedelta

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Fund, FundMetrics, Price
from app.services.metrics import compute_fund_metrics

log = logging.getLogger(__name__)

# Risksiz getiri yerine kullanılan kategori. Para piyasası fonları kısa vadeli,
# çok düşük riskli araçlara yatırım yaptığından getirileri piyasadaki risksiz
# faizin iyi bir yaklaşığıdır ve veriden otomatik hesaplanır.
RISK_FREE_CATEGORY = "Para Piyasası"


# Metrikler en fazla 1 yıl geriye bakar (yılbaşı getirisi de dahil). Biraz pay bırakıp
# sadece son ~13 ayı okuyoruz; 5 yıllık verinin tamamını okumaktan çok daha hızlı.
LOOKBACK_DAYS = 400


def load_prices(db: Session) -> pd.DataFrame:
    latest = db.scalar(select(func.max(Price.date)))
    if latest is None:
        return pd.DataFrame(columns=["code", "date", "price"])
    since = latest - timedelta(days=LOOKBACK_DAYS)
    rows = db.execute(select(Price.fund_code, Price.date, Price.price).where(Price.date >= since)).all()
    df = pd.DataFrame(rows, columns=["code", "date", "price"])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def estimate_risk_free_rate(db: Session, prices: pd.DataFrame) -> float | None:
    """Para piyasası fonlarının 1 yıllık getirilerinin medyanı."""
    if settings.risk_free_rate is not None:
        return settings.risk_free_rate
    codes = set(db.scalars(select(Fund.code).where(Fund.category == RISK_FREE_CATEGORY)))
    rets = []
    for code, g in prices[prices["code"].isin(codes)].groupby("code"):
        m = compute_fund_metrics(g.set_index("date")["price"])
        if m and m.ret_1y is not None:
            rets.append(m.ret_1y)
    return statistics.median(rets) if rets else None


def recompute_all(db: Session) -> dict:
    t0 = time.time()
    prices = load_prices(db)
    if prices.empty:
        return {"funds": 0, "risk_free_rate": None, "seconds": 0}

    rf = estimate_risk_free_rate(db, prices)
    log.info("Risksiz getiri (yıllık): %s", f"{rf:.2%}" if rf is not None else "hesaplanamadı")

    rows = []
    for code, g in prices.groupby("code"):
        m = compute_fund_metrics(g.set_index("date")["price"], risk_free_rate=rf)
        if m:
            rows.append(FundMetrics(fund_code=code, **asdict(m)))

    db.execute(delete(FundMetrics))
    db.add_all(rows)
    db.commit()
    result = {"funds": len(rows), "risk_free_rate": rf, "seconds": round(time.time() - t0, 1)}
    log.info("Metrikler hesaplandı: %s", result)
    return result
