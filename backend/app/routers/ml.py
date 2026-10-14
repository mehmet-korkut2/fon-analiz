from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.job import latest_report
from app.ml.report import GROUP_LABELS
from app.models import Forecast
from app.schemas import ForecastOut, MlPerformanceOut

router = APIRouter(tags=["ml"])

FORECAST_NOTE = ("Bu bir ML tahmini değildir; testlerde en isabetli yöntem fonun geçmiş ortalama getirisinin "
                 "sürmesi varsayımı çıktı.")


@router.get("/funds/{code}/forecast", response_model=ForecastOut)
def fund_forecast(code: str, db: Session = Depends(get_db)):
    """Gelecek 1 ay (21 işlem günü) için geçmiş eğilime dayalı tahmin (drift) ve konformal %80 aralık."""
    code = code.upper()
    f = db.scalars(select(Forecast).where(Forecast.fund_code == code)).first()
    if f is None:
        raise HTTPException(404, f"{code} için tahmin yok (işleme kapatılmış, verisi eski ya da 1 yıllık geçmişi olmayan fon).")
    model_note = None
    rep = latest_report(db)
    if rep:
        v = next((v for v in rep.payload.get("verdicts", []) if v["group"] == f.risk_group), None)
        if v:
            # sayıya göre değişen ek ("9'unda", "4'ünde") yerine ek gerektirmeyen biçim
            model_note = (f"LightGBM bu risk grubunda {'referansı geçti' if v['success'] else 'basit referansı (drift) geçemedi'} "
                          f"(daha isabetli olduğu ay: {v['wins']} / {v['months']}).")
    return ForecastOut(
        code=code, as_of=f.as_of, horizon_days=f.horizon_days, method=f.method,
        method_label="Geçmiş eğilime dayalı tahmin", pred_return=f.pred_return, lo=f.lo, hi=f.hi,
        risk_group=f.risk_group, risk_group_label=GROUP_LABELS.get(f.risk_group, f.risk_group), coverage=f.coverage,
        note=FORECAST_NOTE, model_note=model_note,
    )


@router.get("/ml/performance", response_model=MlPerformanceOut)
def ml_performance(db: Session = Depends(get_db)):
    """Son walk-forward değerlendirme raporu (bütün modeller, risk grupları, keşif varyantı, ARIMA)."""
    rep = latest_report(db)
    if rep is None:
        raise HTTPException(404, "Model değerlendirmesi henüz yapılmadı (gece güncellemesi ya da scripts/ml_degerlendir --kaydet).")
    return MlPerformanceOut(created_at=rep.created_at.strftime("%Y-%m-%d %H:%M"), data_as_of=rep.data_as_of, report=rep.payload)
