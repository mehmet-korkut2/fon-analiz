from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Fund
from app.routers.funds import fund_out, stale_cutoff
from app.schemas import (
    BacktestFund,
    BacktestOut,
    PerformanceOut,
    PerfPoint,
    PortfolioFund,
    RecommendationItem,
    RecommendationsOut,
    StatsOut,
)
from app.services import recommender as R
from app.services.risk_survey import PROFILE_LABELS, PROFILE_RULES

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

Profile = Literal["temkinli", "dengeli", "agresif"]
BENCHMARK_LABEL = "Para piyasası fonlarının medyanı"


def _stats(d: dict) -> StatsOut:
    return StatsOut(total_return=d["return"], volatility=d["volatility"], max_drawdown=d["max_drawdown"])


def _perf(p: R.Performance | None) -> PerformanceOut | None:
    if p is None:
        return None
    return PerformanceOut(
        start=p.start, end=p.end, portfolio=_stats(p.portfolio), benchmark=_stats(p.benchmark),
        benchmark_label=BENCHMARK_LABEL, benchmark_funds=p.benchmark_funds,
        series=[PerfPoint(date=d.date(), portfolio=round(r.portfolio, 3), benchmark=round(r.benchmark, 3))
                for d, r in p.series.iterrows()],
    )


def _portfolio(rec: R.Recommendation, perf: R.Performance | None) -> list[PortfolioFund]:
    n = len(rec.portfolio)
    return [
        PortfolioFund(code=r.code, name=r.name, category=r.category, weight=1 / n,
                      period_return=perf.funds.get(r.code) if perf else None)
        for r in rec.portfolio.itertuples()
    ]


@router.get("", response_model=RecommendationsOut)
def recommendations(
    profile: Profile,
    qualified: bool = Query(False, description="Nitelikli yatırımcı: serbest fonlar da önerilir"),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Profile göre öneriler ve örnek portföy. Portföyün son 1 yıllık performansı, fonlar aynı
    dönemin verisiyle seçildiği için iyimserdir; gerçek test için /recommendations/backtest."""
    rec = R.recommend(db, profile, qualified, limit)
    codes = list(rec.items["code"])
    funds = {f.code: f for f in db.scalars(
        select(Fund).where(Fund.code.in_(codes)).options(joinedload(Fund.metrics))).unique()}
    cutoff = stale_cutoff(db)
    items = []
    for rank, row in enumerate(rec.items.itertuples(), start=1):
        reasons, caution = rec.reasons[row.code]
        items.append(RecommendationItem(
            **fund_out(funds[row.code], cutoff).model_dump(), rank=rank, score=round(row.score, 4),
            components={c: round(getattr(row, c), 4) for c in R.COMPONENTS}, low_volatility=bool(row.low_vol),
            reasons=reasons, caution=caution,
        ))
    perf = None
    if not rec.portfolio.empty and rec.as_of:
        start = (pd.Timestamp(rec.as_of) - pd.DateOffset(months=12)).date()
        perf = R.performance(db, list(rec.portfolio["code"]), start, rec.as_of, R.money_market_codes(db))
    rule = PROFILE_RULES[profile]
    return RecommendationsOut(
        profile=profile, label=PROFILE_LABELS[profile], qualified=qualified, as_of=rec.as_of,
        risk_free_rate=rec.risk_free_rate, pool_size=rec.pool_size, risk_range=rule.risk_range,
        max_volatility=rule.max_volatility, weights=R.WEIGHTS[profile], ra_mode=R.RA_MODE[profile],
        category_limit=R.CATEGORY_LIMIT, items=items, portfolio=_portfolio(rec, perf), performance=_perf(perf),
    )


@router.get("/backtest", response_model=BacktestOut)
def backtest(profile: Profile, qualified: bool = False, db: Session = Depends(get_db)):
    """Seçimi 12 ay önceki veriyle yapar, sonraki 12 ayın performansını para piyasası medyanıyla karşılaştırır."""
    bt = R.backtest(db, profile, qualified)
    if bt is None:
        return BacktestOut(profile=profile, qualified=qualified, selection_date=None, risk_free_rate=None,
                           pool_size=0, recommendations=[], portfolio=[], performance=None)
    rec = bt.recommendation
    return BacktestOut(
        profile=profile, qualified=qualified, selection_date=bt.selection_date, risk_free_rate=rec.risk_free_rate,
        pool_size=rec.pool_size,
        recommendations=[
            BacktestFund(code=r.code, name=r.name, category=r.category,
                         risk_level=None if pd.isna(r.risk_level) else int(r.risk_level),
                         score=round(r.score, 4), ret_1y_before=r.ret_1y, reasons=rec.reasons[r.code][0])
            for r in rec.items.itertuples()
        ],
        portfolio=_portfolio(rec, bt.performance), performance=_perf(bt.performance),
    )
