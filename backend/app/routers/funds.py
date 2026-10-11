from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Fund, Price
from app.schemas import FundOut

router = APIRouter(prefix="/funds", tags=["funds"])

# Veritabanı boşken (TEFAS verisi henüz yüklenmediyse) gösterilen örnek veri
SAMPLE_FUNDS = [
    FundOut(code="AAA", name="Örnek Hisse Senedi Fonu", category="Hisse Senedi", price=1.2345),
    FundOut(code="BBB", name="Örnek Para Piyasası Fonu", category="Para Piyasası", price=2.5000),
    FundOut(code="CCC", name="Örnek Altın Fonu", category="Kıymetli Madenler", price=0.8765),
]


@router.get("", response_model=list[FundOut])
def list_funds(category: str | None = None, db: Session = Depends(get_db)):
    if db.scalar(select(func.count()).select_from(Fund)) == 0:
        return [f for f in SAMPLE_FUNDS if not category or f.category == category]

    # Her fonun en son fiyatı
    last_date = (
        select(Price.fund_code, func.max(Price.date).label("d"))
        .group_by(Price.fund_code)
        .subquery()
    )
    stmt = (
        select(Fund, Price.price, Price.date)
        .outerjoin(last_date, last_date.c.fund_code == Fund.code)
        .outerjoin(Price, (Price.fund_code == Fund.code) & (Price.date == last_date.c.d))
        .order_by(Fund.code)
    )
    if category:
        stmt = stmt.where(Fund.category == category)

    return [
        FundOut(code=f.code, name=f.name, category=f.category, price=price, price_date=d)
        for f, price, d in db.execute(stmt)
    ]
