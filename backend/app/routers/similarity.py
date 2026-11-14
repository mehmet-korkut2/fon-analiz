"""Benzer fonlar, kümeler ve seçilen fonların korelasyonu (app/ml/similarity.py)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml import similarity as S
from app.models import Fund, FundMetrics
from app.schemas import ClusterOut, ClustersOut, CorrelationOut, FundSimilarityOut, SimilarFundOut

router = APIRouter(tags=["benzerlik"])

MAX_CODES = 25
SIMILAR_NOTE = ("Benzerlik, son 1 yılın haftalık getirilerinin korelasyonudur: iki fonun fiyatı ne kadar birlikte "
                "hareket etmiş. Geçmişteki birlikte hareket gelecekte sürmeyebilir; yatırım tavsiyesi değildir.")
CORR_NOTE = ("Korelasyon son 1 yılın haftalık getirilerinden hesaplanır (1: tamamen birlikte, 0: ilişkisiz, -1: ters). "
             f"%{S.HIGH_CORR * 100:g} ve üstü çiftler büyük ölçüde aynı hareket eder; ikisini birlikte tutmak riski azaltmaz.")


@router.get("/funds/{code}/similar", response_model=FundSimilarityOut)
def similar(code: str, db: Session = Depends(get_db)):
    """Fona en çok benzeyen 5 fon ve fonun kümesi (ayda bir hesaplanır)."""
    code = code.upper()
    if db.get(Fund, code) is None:
        raise HTTPException(404, f"{code} kodlu fon bulunamadı.")
    res = S.fund_similarity(db, code)
    if res is None:
        return FundSimilarityOut(code=code, available=False, reason="Benzerlik henüz hesaplanmadı.", note=SIMILAR_NOTE)
    run = res["run"]
    base = dict(code=code, as_of=run.data_as_of, computed_at=run.created_at.isoformat(timespec="minutes"), note=SIMILAR_NOTE)
    if res["row"] is None:
        return FundSimilarityOut(available=False, reason=(
            "Bu fon benzerlik hesabına girmedi: en az 1 yıllık güncel fiyat verisi olan, işleme açık fonlar karşılaştırılır."), **base)
    codes = [n.neighbor_code for n in res["neighbors"]]
    info = {c: (n, cat) for c, n, cat in db.execute(select(Fund.code, Fund.name, Fund.category).where(Fund.code.in_(codes))).all()}
    rets = dict(db.execute(select(FundMetrics.fund_code, FundMetrics.ret_1y).where(FundMetrics.fund_code.in_(codes))).all())
    neighbors = [SimilarFundOut(code=n.neighbor_code, name=info.get(n.neighbor_code, (None, None))[0],
                                category=info.get(n.neighbor_code, (None, None))[1], corr=n.corr, ret_1y=rets.get(n.neighbor_code))
                 for n in res["neighbors"]]
    return FundSimilarityOut(available=True, cluster=ClusterOut(**res["cluster"]) if res["cluster"] else None,
                             fund_silhouette=res["row"].silhouette, neighbors=neighbors, **base)


@router.get("/correlation", response_model=CorrelationOut)
def correlation(
    codes: str = Query(..., description="Virgülle ayrılmış fon kodları, ör. TTE,YHZ,OJK"),
    weights: str | None = Query(None, description="İsteğe bağlı ağırlıklar (aynı sırayla), ör. 0.5,0.3,0.2"),
    db: Session = Depends(get_db),
):
    """Seçilen fonların korelasyon matrisi, %90 ve üstü çiftler, etkin bağımsız fon sayısı (anlık hesaplanır)."""
    raw = [c.strip().upper() for c in codes.split(",")]
    if any(not c for c in raw):
        raise HTTPException(422, "Fon kodları virgülle ayrılmalı.")
    if len(raw) > MAX_CODES:
        raise HTTPException(422, f"En fazla {MAX_CODES} fon seçilebilir.")
    w = None
    if weights:
        try:
            w = [float(x) for x in weights.split(",")]
        except ValueError:
            raise HTTPException(422, "Ağırlıklar sayı olmalı.") from None
        if len(w) != len(raw) or any(x < 0 for x in w):
            raise HTTPException(422, "Her fon için negatif olmayan bir ağırlık verilmeli.")
        merged: dict[str, float] = {}
        for c, x in zip(raw, w):
            merged[c] = merged.get(c, 0) + x
        raw, w = list(merged), list(merged.values())
    res = S.analyze(db, raw, w)
    names = dict(db.execute(select(Fund.code, Fund.name).where(Fund.code.in_(res["codes"]))).all())
    return CorrelationOut(names=names, note=CORR_NOTE, **res)


@router.get("/clusters", response_model=ClustersOut)
def clusters(db: Session = Depends(get_db)):
    """Son kümeleme hesabı: yöntem, küme sayısı, kategorilerle örtüşme, kararlılık, kümeler."""
    run = S.latest_run(db)
    if run is None:
        raise HTTPException(404, "Kümeleme henüz hesaplanmadı (python -m scripts.benzerlik_hesapla).")
    return ClustersOut(created_at=run.created_at.isoformat(timespec="minutes"), data_as_of=run.data_as_of, report=run.payload)
