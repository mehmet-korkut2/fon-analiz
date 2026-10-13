"""Fon performans metrikleri.

Tüm getiri ve oranlar ondalık kesir olarak döner (0.25 = %25).

Tanımlar (rapor için):
- Dönem getirisi   : son fiyat / dönem başındaki fiyat - 1
                     (dönem başı = o tarihteki veya ondan önceki son fiyat)
- Yılbaşından beri : son fiyat / önceki yılın son fiyatı - 1
- 3 yıllık getiri  : toplam getiri, yıllıklandırılmaz (3 yılda %100 = 2 kat)
- Volatilite       : günlük getirilerin standart sapması × √252 (yıllıklandırılmış)
- Sharpe oranı     : (1 yıllık getiri - risksiz getiri) / 1 yıllık volatilite
- Maksimum düşüş   : 1 yıl içinde bir zirveden sonraki en büyük yüzde kayıp
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

TRADING_DAYS = 252
MIN_POINTS_FOR_RISK = 60  # volatilite ve Sharpe için en az ~3 aylık veri
START_TOLERANCE_DAYS = 7  # dönem başında bu kadar gün içinde fiyat yoksa fon o dönem için çok yeni


# --- Temel fonksiyonlar ---------------------------------------------------

def daily_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change().dropna()


def total_return(prices: pd.Series) -> float:
    return prices.iloc[-1] / prices.iloc[0] - 1


def annual_volatility(prices: pd.Series) -> float:
    return daily_returns(prices).std() * np.sqrt(TRADING_DAYS)


def sharpe_ratio(prices: pd.Series, risk_free_rate: float = 0.0) -> float:
    r = daily_returns(prices)
    excess = r - risk_free_rate / TRADING_DAYS
    return excess.mean() / excess.std() * np.sqrt(TRADING_DAYS)


def max_drawdown(prices: pd.Series) -> float:
    peak = prices.cummax()
    return (prices / peak - 1).min()


# --- Bir fonun tüm metrikleri ----------------------------------------------

@dataclass
class FundMetricValues:
    as_of: date
    last_price: float
    daily_change: float | None
    ret_1m: float | None
    ret_3m: float | None
    ret_6m: float | None
    ret_1y: float | None
    ret_ytd: float | None
    ret_3y: float | None
    volatility_1y: float | None
    sharpe_1y: float | None
    max_drawdown_1y: float | None
    data_points: int


def _clean(x) -> float | None:
    if x is None:
        return None
    x = float(x)
    return None if math.isnan(x) or math.isinf(x) else x


def price_on_or_before(prices: pd.Series, when: pd.Timestamp) -> float | None:
    """`when` tarihindeki ya da ondan önceki son fiyat. Fon o tarihte yoksa None."""
    before = prices.loc[:when]
    if before.empty:
        return None
    if (when - before.index[-1]).days > START_TOLERANCE_DAYS:
        return None
    return float(before.iloc[-1])


def period_return(prices: pd.Series, months: int) -> float | None:
    as_of = prices.index[-1]
    start = price_on_or_before(prices, as_of - pd.DateOffset(months=months))
    if not start:
        return None
    return prices.iloc[-1] / start - 1


def ytd_return(prices: pd.Series) -> float | None:
    as_of = prices.index[-1]
    prev_year_end = pd.Timestamp(year=as_of.year - 1, month=12, day=31)
    before = prices.loc[:prev_year_end]
    # Yılbaşı tatilleri yüzünden son işlem günü 31 Aralık'tan birkaç gün önce olabilir
    if before.empty or (prev_year_end - before.index[-1]).days > START_TOLERANCE_DAYS:
        return None
    return prices.iloc[-1] / before.iloc[-1] - 1


def compute_fund_metrics(prices: pd.Series, risk_free_rate: float | None = None) -> FundMetricValues | None:
    """`prices`: tarih indeksli fiyat serisi. Boşsa None döner."""
    prices = prices.dropna()
    prices = prices[prices > 0].sort_index()
    if prices.empty:
        return None
    prices.index = pd.to_datetime(prices.index)

    as_of = prices.index[-1]
    window = prices.loc[as_of - pd.DateOffset(years=1):]
    ret_1y = period_return(prices, 12)

    vol = mdd = sharpe = None
    if len(window) >= MIN_POINTS_FOR_RISK:
        vol = _clean(annual_volatility(window))
        mdd = _clean(max_drawdown(window))
        if ret_1y is not None and vol and risk_free_rate is not None:
            sharpe = _clean((ret_1y - risk_free_rate) / vol)

    return FundMetricValues(
        as_of=as_of.date(),
        last_price=float(prices.iloc[-1]),
        daily_change=_clean(prices.iloc[-1] / prices.iloc[-2] - 1) if len(prices) > 1 else None,
        ret_1m=_clean(period_return(prices, 1)),
        ret_3m=_clean(period_return(prices, 3)),
        ret_6m=_clean(period_return(prices, 6)),
        ret_1y=_clean(ret_1y),
        ret_ytd=_clean(ytd_return(prices)),
        ret_3y=_clean(period_return(prices, 36)),
        volatility_1y=vol,
        sharpe_1y=sharpe,
        max_drawdown_1y=mdd,
        data_points=len(window),
    )
