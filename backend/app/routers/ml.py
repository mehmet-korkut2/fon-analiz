from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml import horizons as H
from app.ml.features import HORIZON
from app.ml.job import latest_report
from app.ml.report import GROUP_LABELS
from app.models import SOURCE_BACKFILL, SOURCE_LIVE
from app.schemas import ForecastOut, MlPerformanceOut, ScorecardOut

router = APIRouter(tags=["ml"])

FORECAST_NOTE = ("Bu bir ML tahmini değildir; testlerde en isabetli yöntem fonun geçmiş ortalama getirisinin "
                 "sürmesi varsayımı çıktı.")
SCORECARD_NOTE = ("Karne, geçmiş tahminlerin gerçekleşenle karşılaştırmasıdır; geleceğe dair bir güvence vermez. "
                  "%80 aralık, tahminlerin yaklaşık 10'da 8'inde gerçekleşen fiyatı içermesi için kurulur.")
BACKFILL_NOTE = ("Geriye dönük hesaplanmıştır: bu tahmin o gün kaydedilmedi, sonradan yalnızca o tarihe kadarki "
                 "fiyatlar ve o tarihe kadar gerçekleşmiş hatalarla hesaplandı.")


def _coverage(db: Session, group: str, horizon: int = HORIZON) -> float | None:
    """Aralığın test dönemindeki kapsama oranı (ufka göre değerlendirme; yoksa eski 21 günlük aralık)."""
    rep = latest_report(db)
    if rep is None:
        return None
    rows = (rep.payload.get("horizons") or {}).get("rows") or []
    r = next((r for r in rows if r["horizon"] == horizon and r["group"] == group), None)
    if r:
        return r["coverage"]
    return (rep.payload.get("drift_interval") or {}).get(group, {}).get("coverage")


@router.get("/funds/{code}/forecast", response_model=ForecastOut)
def fund_forecast(code: str, db: Session = Depends(get_db)):
    """Gelecek 1 ay (21 işlem günü) için geçmiş eğilime dayalı tahmin (drift), konformal %80 aralık ve
    1..21 günlük yol (her ufka ayrı kalibre edilmiş aralık)."""
    code = code.upper()
    f = H.latest_forecasts(db, [code]).get(code)
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
        code=code, as_of=f.as_of, horizon_days=HORIZON, method=f.method, method_version=f.method_version,
        method_label="Geçmiş eğilime dayalı tahmin", pred_return=f.pred_return, lo=f.lo, hi=f.hi,
        risk_group=f.risk_group, risk_group_label=GROUP_LABELS.get(f.risk_group, f.risk_group),
        coverage=_coverage(db, f.risk_group), note=FORECAST_NOTE, model_note=model_note, source=f.source, path=f.path,
    )


@router.get("/funds/{code}/forecast-scorecard", response_model=ScorecardOut)
def fund_forecast_scorecard(code: str, as_of: date | None = None,
                            source: str | None = Query(None, pattern=f"^({SOURCE_LIVE}|{SOURCE_BACKFILL})$"),
                            db: Session = Depends(get_db)):
    """Tahmin karnesi: son 30 tahmin günü, seçilen günün 1..21 günlük tahminleri ve gerçekleşenler,
    ufuk özeti (1 gün, 2 gün, 1 hafta, 2 hafta, 1 ay; canlı ve geriye dönük ayrı)."""
    code = code.upper()
    card = H.fund_scorecard(db, code, as_of, source)
    if card is None:
        raise HTTPException(404, f"{code} için kayıtlı tahmin yok.")
    if as_of is not None and card["selected"] is None:
        raise HTTPException(404, f"{code} için {as_of} tarihli tahmin yok.")
    return ScorecardOut(**card, note=SCORECARD_NOTE, backfill_note=BACKFILL_NOTE)


@router.get("/ml/performance", response_model=MlPerformanceOut)
def ml_performance(db: Session = Depends(get_db)):
    """Son walk-forward değerlendirme raporu (bütün modeller, risk grupları, keşif varyantı, ARIMA,
    ufka göre aralık) ve tahmin karnesinin bütün fonlar üzerinden özeti."""
    rep = latest_report(db)
    if rep is None:
        raise HTTPException(404, "Model değerlendirmesi henüz yapılmadı (gece güncellemesi ya da scripts/ml_degerlendir --kaydet).")
    s = H.latest_summary(db)
    return MlPerformanceOut(created_at=rep.created_at.strftime("%Y-%m-%d %H:%M"), data_as_of=rep.data_as_of, report=rep.payload,
                            scorecard=s.payload if s else None)
