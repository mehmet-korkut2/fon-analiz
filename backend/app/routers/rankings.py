from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, contains_eager

from app.database import get_db
from app.models import Fund, FundMetrics
from app.routers.funds import fund_out, is_fresh, stale_cutoff
from app.services.fund_status import is_tradable
from app.schemas import RankedFund, RankingList, RankingsOut

router = APIRouter(prefix="/rankings", tags=["rankings"])

ReturnMetric = Literal["ret_1m", "ret_3m", "ret_6m", "ret_ytd", "ret_1y", "ret_3y"]


@router.get("", response_model=RankingsOut)
def rankings(
    category: str | None = None,
    period: ReturnMetric = Query("ret_1y", description="Getiri sıralamasının dönemi"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """En iyi getiri, en düşük volatilite ve en iyi Sharpe listeleri.

    Eski verili (son fiyatı güncel olmayan), kapanmış ve SPK kararıyla işleme kapatılan fonlar sıralamaya girmez.
    """
    cutoff = stale_cutoff(db)
    base = (
        select(Fund)
        .join(FundMetrics)
        .where(Fund.is_active.is_(True), is_fresh(cutoff), is_tradable())
        .options(contains_eager(Fund.metrics))
    )
    if category:
        base = base.where(Fund.category == category)

    def top(key: str, metric: str, order: str) -> RankingList:
        col = getattr(FundMetrics, metric)
        stmt = base.where(col.is_not(None)).order_by(col.desc() if order == "desc" else col.asc(), Fund.code).limit(limit)
        items = [
            RankedFund(**fund_out(f, cutoff).model_dump(), rank=i, value=getattr(f.metrics, metric))
            for i, f in enumerate(db.scalars(stmt).unique(), start=1)
        ]
        return RankingList(key=key, metric=metric, order=order, items=items)

    eligible = db.scalar(select(func.count()).select_from(base.subquery()))
    return RankingsOut(
        as_of=db.scalar(select(func.max(FundMetrics.as_of))),
        category=category,
        eligible=eligible,
        lists=[top("return", period, "desc"), top("volatility", "volatility_1y", "asc"), top("sharpe", "sharpe_1y", "desc")],
    )
