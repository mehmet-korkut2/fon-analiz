"""Gece güncellemesindeki ML işi.

- Her gece: son fiyat gününde her fon için 1..21 işlem günü ufkunda drift tahmini ve ufka + risk grubuna
  göre konformal %80 aralık `forecast_days` tablosuna canlı olarak eklenir; son 60 işlem gününden tahmini
  olmayan günler geriye dönük hesaplanır (app/ml/horizons.py). Kayıtlar silinmez. Ardından bütün fonların
  karne özeti `forecast_summaries`'e yazılır.
- Rapor 28 günden eskiyse (~1-2 dk): walk-forward değerlendirme ARIMA'sız yeniden yapılıp `ml_reports`
  tablosuna yazılır. ARIMA ve hiperparametre ayarı yavaş olduğu için sadece betikle çalışır
  (scripts/ml_degerlendir --arima --kaydet); önceki raporun ARIMA bölümü tarihiyle korunur.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

import pandas as pd
from sqlalchemy import insert, inspect, select, text
from sqlalchemy.orm import Session

from app.ml import horizons as H
from app.ml.features import build_dataset, load_panel, month_starts
from app.ml.report import build_report, split_origins
from app.ml.trading_calendar import target_dates
from app.models import SOURCE_LIVE, ForecastDay, MlReport, Price

log = logging.getLogger(__name__)
REPORT_MAX_AGE_DAYS = 28
LEGACY_VERSION = "v0"  # eski forecasts tablosunun yöntemi (H.METHOD_VERSIONS)


def latest_report(db: Session) -> MlReport | None:
    return db.scalars(select(MlReport).order_by(MlReport.created_at.desc(), MlReport.id.desc()).limit(1)).first()


def save_report(db: Session, rep: dict) -> MlReport:
    row = MlReport(data_as_of=date.fromisoformat(rep["data_as_of"]), payload=rep)
    db.add(row)
    db.commit()
    return row


def migrate_legacy(db: Session) -> int:
    """Eski `forecasts` tablosu (her gece silinip yazılan, yalnızca 21 günlük tahmin) varsa kayıtları
    `forecast_days`'e canlı olarak aktarılır ve tablo kaldırılır. Bir kez çalışır."""
    if "forecasts" not in inspect(db.get_bind()).get_table_names():
        return 0
    old = db.execute(text("SELECT fund_code, as_of, horizon_days, method, pred_return, lo, hi, risk_group, created_at "
                          "FROM forecasts")).all()
    rows = []
    days = sorted(r[0] for r in db.execute(select(Price.date).distinct()).all())
    for code, as_of, h, _method, pred, lo, hi, group, created in old:
        as_of = date.fromisoformat(str(as_of))
        base = db.scalar(select(Price.price).where(Price.fund_code == code, Price.date == as_of))
        if base is None:
            continue
        rows.append({"fund_code": code, "as_of": as_of, "base_price": base, "horizon": int(h),
                     "target_date": target_dates(as_of, int(h), days)[-1], "pred_price": base * (1 + pred),
                     "lo_price": base * (1 + lo), "hi_price": base * (1 + hi), "method": H.METHOD,
                     "method_version": LEGACY_VERSION, "source": SOURCE_LIVE,
                     "risk_group": group, "calib_n": None,
                     "created_at": datetime.fromisoformat(str(created)) if created else None})
    if rows:
        db.execute(insert(ForecastDay), rows)
    db.execute(text("DROP TABLE forecasts"))
    db.commit()
    log.info("Eski forecasts tablosundan %s kayıt aktarıldı", len(rows))
    return len(rows)


def run(db: Session, force_report: bool = False) -> dict:
    panel = load_panel(db)
    data = build_dataset(panel, month_starts(panel)) if len(panel.prices.index) > 0 else pd.DataFrame()
    _, test = split_origins(data) if not data.empty else ([], [])
    if not test:
        # walk-forward için yeterli geçmiş yok (ör. yeni kurulum ya da test veritabanı): atla, hata sayma
        log.info("ML işi atlandı: yeterli geçmiş veri yok")
        return {"skipped": "yeterli geçmiş veri yok"}
    dp = H.DriftPanel(panel)
    last = latest_report(db)
    age = (datetime.now() - last.created_at).days if last else None
    # ufka göre değerlendirmesi olmayan eski rapor da yenilenir
    refreshed = force_report or last is None or age >= REPORT_MAX_AGE_DAYS or "horizons" not in last.payload
    if refreshed:
        rep = build_report(panel, data, do_tune=False, arima=False, explore=True, log=log.info, dp=dp)
        if last and last.payload.get("arima"):
            rep["arima"] = last.payload["arima"]
            rep["arima_as_of"] = last.payload.get("arima_as_of") or last.payload["data_as_of"]
        if last and last.payload.get("tuning"):
            rep["tuning"] = last.payload["tuning"]
        save_report(db, rep)
    migrated = migrate_legacy(db)
    stored = H.store(db, dp)
    H.save_summary(db, H.summarize_all(db, dp))
    result = {"forecasts": stored["live"], "backfill": stored["backfill"], "backfill_days": stored["backfill_days"],
              "migrated": migrated, "report_refreshed": refreshed}
    log.info("ML işi: %s", result)
    return result
