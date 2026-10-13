from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Fund, FundMetrics, Price
from app.schemas import CategoryOut, FundDetail, FundOut, FundPage, MetricsOut, PricePoint

router = APIRouter(prefix="/funds", tags=["funds"])

# Veritabanı boşken (TEFAS verisi henüz yüklenmediyse) gösterilen örnek veri
SAMPLE_FUNDS = [
    FundOut(code="AAA", name="Örnek Hisse Senedi Fonu", category="Hisse Senedi", risk_level=6, price=1.2345),
    FundOut(code="BBB", name="Örnek Para Piyasası Fonu", category="Para Piyasası", risk_level=1, price=2.5000),
    FundOut(code="CCC", name="Örnek Altın Fonu", category="Kıymetli Madenler", risk_level=5, price=0.8765),
]

SortField = Literal["code", "name", "ret_1m", "ret_3m", "ret_6m", "ret_1y", "ret_ytd", "volatility_1y", "sharpe_1y", "max_drawdown_1y", "risk_level"]
SORT_COLUMNS = {
    "code": Fund.code, "name": Fund.name, "risk_level": Fund.risk_level,
    "ret_1m": FundMetrics.ret_1m, "ret_3m": FundMetrics.ret_3m, "ret_6m": FundMetrics.ret_6m,
    "ret_1y": FundMetrics.ret_1y, "ret_ytd": FundMetrics.ret_ytd, "volatility_1y": FundMetrics.volatility_1y,
    "sharpe_1y": FundMetrics.sharpe_1y, "max_drawdown_1y": FundMetrics.max_drawdown_1y,
}


def tr_upper(s: str) -> str:
    """Türkçe büyük harf: 'i' -> 'İ', 'ı' -> 'I' (Python'un upper()'ı bunu yapmaz)."""
    return s.replace("i", "İ").replace("ı", "I").upper()


def _to_out(f: Fund) -> FundOut:
    m = f.metrics
    return FundOut(
        code=f.code, name=f.name, category=f.category, risk_level=f.risk_level,
        price=m.last_price if m else None, price_date=m.as_of if m else None,
        metrics=MetricsOut.model_validate(m) if m else None,
    )


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
    db: Session = Depends(get_db),
):
    if db.scalar(select(func.count()).select_from(Fund)) == 0:
        items = [f for f in SAMPLE_FUNDS if not category or f.category == category]
        return FundPage(items=items, total=len(items), page=1, page_size=page_size, sample=True)

    stmt = select(Fund).outerjoin(FundMetrics)
    if not include_inactive:
        stmt = stmt.where(Fund.is_active.is_(True))
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
    items = [_to_out(f) for f in db.scalars(stmt).unique()]
    return FundPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Fund.category, func.count())
        .where(Fund.category.is_not(None), Fund.is_active.is_(True))
        .group_by(Fund.category)
        .order_by(func.count().desc())
    ).all()
    return [CategoryOut(name=c, count=n) for c, n in rows]


@router.get("/{code}", response_model=FundDetail)
def get_fund(code: str, db: Session = Depends(get_db)):
    f = db.get(Fund, code.upper(), options=[joinedload(Fund.metrics)])
    if f is None:
        raise HTTPException(404, f"{code.upper()} kodlu fon bulunamadı.")
    out = FundDetail(**_to_out(f).model_dump(), fund_type=f.fund_type, is_active=f.is_active)

    if f.category and f.metrics and f.metrics.ret_1y is not None:
        peers = (
            select(FundMetrics.ret_1y)
            .join(Fund)
            .where(Fund.category == f.category, FundMetrics.ret_1y.is_not(None))
        ).subquery()
        out.category_size = db.scalar(select(func.count()).select_from(peers))
        out.category_rank_1y = 1 + db.scalar(
            select(func.count()).select_from(peers).where(peers.c.ret_1y > f.metrics.ret_1y)
        )
    return out


@router.get("/{code}/prices", response_model=list[PricePoint])
def get_prices(
    code: str,
    months: int = Query(12, ge=1, le=60, description="Kaç aylık geçmiş"),
    db: Session = Depends(get_db),
):
    code = code.upper()
    last = db.scalar(select(func.max(Price.date)).where(Price.fund_code == code))
    if last is None:
        raise HTTPException(404, f"{code} için fiyat verisi yok.")
    since = last - timedelta(days=round(months * 30.44))
    rows = db.execute(
        select(Price.date, Price.price)
        .where(Price.fund_code == code, Price.date >= since)
        .order_by(Price.date)
    ).all()
    return [PricePoint(date=d, price=p) for d, p in rows]
