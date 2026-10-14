"""Gece güncellemesindeki ML işi.

- Her gece (~15 sn): son fiyat tarihindeki özelliklerle her fon için drift tahmini ve risk grubuna göre
  konformal %80 aralık hesaplanıp `forecasts` tablosuna yazılır.
- Rapor 28 günden eskiyse (~1-2 dk): walk-forward değerlendirme ARIMA'sız yeniden yapılıp `ml_reports`
  tablosuna yazılır. ARIMA ve hiperparametre ayarı yavaş olduğu için sadece betikle çalışır
  (scripts/ml_degerlendir --arima --kaydet); önceki raporun ARIMA bölümü tarihiyle korunur.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ml.features import HORIZON, build_dataset, features_at, load_panel, month_starts
from app.ml.report import build_report, split_origins
from app.models import Forecast, Fund, MlReport
from app.services.fund_status import STATUS_ACTIVE

log = logging.getLogger(__name__)
REPORT_MAX_AGE_DAYS = 28


def latest_report(db: Session) -> MlReport | None:
    return db.scalars(select(MlReport).order_by(MlReport.created_at.desc(), MlReport.id.desc()).limit(1)).first()


def save_report(db: Session, rep: dict) -> MlReport:
    row = MlReport(data_as_of=date.fromisoformat(rep["data_as_of"]), payload=rep)
    db.add(row)
    db.commit()
    return row


def store_forecasts(db: Session, panel, intervals: dict) -> int:
    """Son fiyat tarihindeki drift tahmini + konformal aralık. İşleme kapatılmış fonlar hariç."""
    t = panel.prices.index[-1]
    f = features_at(panel, t)
    closed = set(db.scalars(select(Fund.code).where(Fund.status.is_not(None), Fund.status != STATUS_ACTIVE)))
    rows = []
    for code, r in f.iterrows():
        iv = intervals.get(r["risk_group"]) or {}
        if code in closed or pd.isna(r["drift"]) or iv.get("q10") is None:
            continue
        pred = float(r["drift"])
        rows.append(Forecast(fund_code=code, as_of=t.date(), horizon_days=HORIZON, method="drift", pred_return=pred,
                             lo=pred + iv["q10"], hi=pred + iv["q90"], risk_group=r["risk_group"], coverage=iv.get("coverage")))
    db.execute(delete(Forecast))
    db.add_all(rows)
    db.commit()
    return len(rows)


def run(db: Session, force_report: bool = False) -> dict:
    panel = load_panel(db)
    data = build_dataset(panel, month_starts(panel)) if len(panel.prices.index) > 0 else pd.DataFrame()
    _, test = split_origins(data) if not data.empty else ([], [])
    if not test:
        # walk-forward için yeterli geçmiş yok (ör. yeni kurulum ya da test veritabanı): atla, hata sayma
        log.info("ML işi atlandı: yeterli geçmiş veri yok")
        return {"skipped": "yeterli geçmiş veri yok"}
    last = latest_report(db)
    age = (datetime.now() - last.created_at).days if last else None
    refreshed = force_report or last is None or age >= REPORT_MAX_AGE_DAYS
    if refreshed:
        rep = build_report(panel, data, do_tune=False, arima=False, explore=True, log=log.info)
        if last and last.payload.get("arima"):
            rep["arima"] = last.payload["arima"]
            rep["arima_as_of"] = last.payload.get("arima_as_of") or last.payload["data_as_of"]
        if last and last.payload.get("tuning"):
            rep["tuning"] = last.payload["tuning"]
        save_report(db, rep)
        intervals = rep["drift_interval"]
    else:
        intervals = last.payload["drift_interval"]
    n = store_forecasts(db, panel, intervals)
    result = {"forecasts": n, "report_refreshed": refreshed}
    log.info("ML işi: %s", result)
    return result
