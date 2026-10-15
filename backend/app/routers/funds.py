from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Fund, FundMetrics, Price
from app.schemas import CategoryOut, FundDetail, FundOut, FundPage, MetricsOut, PricePoint, TechnicalOut
from app.services.fund_status import STATUS_ACTIVE, is_tradable
from app.services.metrics import MIN_VOL_FOR_SHARPE
from app.services.metrics_job import STALE_AFTER_DAYS
from app.services.technical import RANGE_DAYS, WARMUP_DAYS, technical
from app.text import tr_upper

router = APIRouter(prefix="/funds", tags=["funds"])

# Veritabanı boşken (TEFAS verisi henüz yüklenmediyse) gösterilen örnek veri
SAMPLE_FUNDS = [
    FundOut(code="AAA", name="Örnek Hisse Senedi Fonu", category="Hisse Senedi", risk_level=6, price=1.2345),
    FundOut(code="BBB", name="Örnek Para Piyasası Fonu", category="Para Piyasası", risk_level=1, price=2.5000),
    FundOut(code="CCC", name="Örnek Altın Fonu", category="Kıymetli Madenler", risk_level=5, price=0.8765),
]

SortField = Literal["code", "name", "ret_1m", "ret_3m", "ret_6m", "ret_1y", "ret_ytd", "ret_3y", "volatility_1y", "sharpe_1y", "max_drawdown_1y", "risk_level"]
SORT_COLUMNS = {
    "code": Fund.code, "name": Fund.name, "risk_level": Fund.risk_level,
    "ret_1m": FundMetrics.ret_1m, "ret_3m": FundMetrics.ret_3m, "ret_6m": FundMetrics.ret_6m,
    "ret_1y": FundMetrics.ret_1y, "ret_ytd": FundMetrics.ret_ytd, "ret_3y": FundMetrics.ret_3y, "volatility_1y": FundMetrics.volatility_1y,
    "sharpe_1y": FundMetrics.sharpe_1y, "max_drawdown_1y": FundMetrics.max_drawdown_1y,
}


def stale_cutoff(db: Session) -> date | None:
    """Bu tarihten önce son fiyatı olan fonlar eski verili sayılır."""
    latest = db.scalar(select(func.max(FundMetrics.as_of)))
    return latest - timedelta(days=STALE_AFTER_DAYS) if latest else None


def is_fresh(cutoff: date | None):
    """Güncel verili fonlar için SQL koşulu (metriği olmayan fonun da verisi yok sayılır)."""
    return FundMetrics.as_of >= cutoff if cutoff else FundMetrics.as_of.is_not(None)


def fund_out(f: Fund, cutoff: date | None) -> FundOut:
    m = f.metrics
    return FundOut(
        code=f.code, name=f.name, category=f.category, risk_level=f.risk_level,
        price=m.last_price if m else None, price_date=m.as_of if m else None,
        is_stale=m is None or (cutoff is not None and m.as_of < cutoff),
        status=f.status or STATUS_ACTIVE, status_note=f.status_note, status_source=f.status_source, status_url=f.status_url,
        metrics=metrics_out(m) if m else None,
    )


LOW_VOL_SHARPE_NOTE = (
    f"Volatilite %{MIN_VOL_FOR_SHARPE * 100:g}'in altında; fiyat neredeyse hiç dalgalanmadığı için Sharpe anlamlı değil."
)


def metrics_out(m: FundMetrics) -> MetricsOut:
    out = MetricsOut.model_validate(m)
    if out.sharpe_1y is None and out.volatility_1y is not None and out.volatility_1y < MIN_VOL_FOR_SHARPE:
        out.sharpe_note = LOW_VOL_SHARPE_NOTE
    return out


@router.get("", response_model=FundPage)
def list_funds(
    q: str | None = Query(None, description="Fon kodu veya adında arama"),
    category: str | None = None,
    risk_min: int | None = Query(None, ge=1, le=7),
    risk_max: int | None = Query(None, ge=1, le=7),
    sort: SortField = "ret_1y",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    include_inactive: bool = False,
    include_stale: bool = Query(False, description="Verisi güncellenmeyen fonları da getir"),
    include_closed: bool = Query(False, description="SPK kararıyla işleme kapatılan fonları da getir"),
    db: Session = Depends(get_db),
):
    if db.scalar(select(func.count()).select_from(Fund)) == 0:
        items = [f for f in SAMPLE_FUNDS if not category or f.category == category]
        return FundPage(items=items, total=len(items), page=1, page_size=page_size, sample=True)

    cutoff = stale_cutoff(db)
    stmt = select(Fund).outerjoin(FundMetrics)
    if not include_inactive:
        stmt = stmt.where(Fund.is_active.is_(True))
    if not include_stale:
        stmt = stmt.where(is_fresh(cutoff))
    if not include_closed:
        stmt = stmt.where(is_tradable())
    if q:
        # TEFAS fon adları Türkçe büyük harfle; SQLite'ın LIKE'ı Türkçe harfleri
        # büyük/küçük eşleştiremediği için aramayı da Türkçe büyük harfe çeviriyoruz.
        term = q.strip()
        likes = {f"%{term}%", f"%{tr_upper(term)}%", f"%{term.upper()}%"}
        stmt = stmt.where(or_(*[c.ilike(x) for x in likes for c in (Fund.code, Fund.name)]))
    if category:
        stmt = stmt.where(Fund.category == category)
    if risk_min:
        stmt = stmt.where(Fund.risk_level >= risk_min)
    if risk_max:
        stmt = stmt.where(Fund.risk_level <= risk_max)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    col = SORT_COLUMNS[sort]
    ordered = col.asc() if order == "asc" else col.desc()
    stmt = (
        stmt.options(joinedload(Fund.metrics))
        .order_by(ordered.nulls_last(), Fund.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [fund_out(f, cutoff) for f in db.scalars(stmt).unique()]
    return FundPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    # Sayılar, listenin varsayılan görünümüyle (eski verili fonlar gizli) tutarlı olsun
    rows = db.execute(
        select(Fund.category, func.count())
        .join(FundMetrics)
        .where(Fund.category.is_not(None), Fund.is_active.is_(True), is_fresh(stale_cutoff(db)), is_tradable())
        .group_by(Fund.category)
        .order_by(func.count().desc())
    ).all()
    return [CategoryOut(name=c, count=n) for c, n in rows]


@router.get("/{code}", response_model=FundDetail)
def get_fund(code: str, db: Session = Depends(get_db)):
    f = db.get(Fund, code.upper(), options=[joinedload(Fund.metrics)])
    if f is None:
        raise HTTPException(404, f"{code.upper()} kodlu fon bulunamadı.")
    cutoff = stale_cutoff(db)
    out = FundDetail(**fund_out(f, cutoff).model_dump(), fund_type=f.fund_type, is_active=f.is_active)

    # Kategori sırası sadece güncel verili ve işlem gören fonlar arasında
    # (eski fonun 1 yıllık getirisi başka döneme ait; işleme kapatılan fona yatırım yapılamaz)
    tradable = out.status == STATUS_ACTIVE
    if f.category and f.metrics and f.metrics.ret_1y is not None and not out.is_stale and tradable:
        peers = (
            select(FundMetrics.ret_1y)
            .join(Fund)
            .where(Fund.category == f.category, FundMetrics.ret_1y.is_not(None), is_fresh(cutoff), is_tradable())
        ).subquery()
        out.category_size = db.scalar(select(func.count()).select_from(peers))
        out.category_rank_1y = 1 + db.scalar(
            select(func.count()).select_from(peers).where(peers.c.ret_1y > f.metrics.ret_1y)
        )
    return out


@router.get("/{code}/prices", response_model=list[PricePoint])
def get_prices(
    code: str,
    months: int = Query(12, ge=1, le=60, description="Kaç aylık geçmiş (start verilmezse)"),
    start: date | None = Query(None, description="Başlangıç tarihi; verilirse months yok sayılır"),
    end: date | None = Query(None, description="Bitiş tarihi (dahil)"),
    db: Session = Depends(get_db),
):
    code = code.upper()
    last = db.scalar(select(func.max(Price.date)).where(Price.fund_code == code))
    if last is None:
        raise HTTPException(404, f"{code} için fiyat verisi yok.")
    if start and end and start > end:
        raise HTTPException(422, "Başlangıç tarihi bitişten sonra olamaz.")
    since = start or last - timedelta(days=round(months * 30.44))
    stmt = select(Price.date, Price.price).where(Price.fund_code == code, Price.date >= since)
    if end:
        stmt = stmt.where(Price.date <= end)
    rows = db.execute(stmt.order_by(Price.date)).all()
    return [PricePoint(date=d, price=p) for d, p in rows]


@router.get("/{code}/technical", response_model=TechnicalOut)
def get_technical(
    code: str,
    months: int = Query(12, ge=1, le=60, description="Ortalama serisi kaç aylık (start verilmezse); prices ile aynı"),
    start: date | None = Query(None, description="Seri başlangıcı; verilirse months yok sayılır"),
    db: Session = Depends(get_db),
):
    """50/200 günlük hareketli ortalama serisi (grafik dönemi için) ve son güne ait özet.

    Özet (trend, 52 haftalık aralık) dönemden bağımsız, her zaman son fiyat gününe göredir.
    """
    code = code.upper()
    last = db.scalar(select(func.max(Price.date)).where(Price.fund_code == code))
    if last is None:
        raise HTTPException(404, f"{code} için fiyat verisi yok.")
    since = start or last - timedelta(days=round(months * 30.44))
    load_from = min(since, last - timedelta(days=RANGE_DAYS)) - timedelta(days=WARMUP_DAYS)
    rows = db.execute(
        select(Price.date, Price.price).where(Price.fund_code == code, Price.date >= load_from).order_by(Price.date)
    ).all()
    return technical([(d, p) for d, p in rows], since)
