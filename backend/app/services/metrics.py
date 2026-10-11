"""Fon performans metrikleri. 3. aşamada (Backend ve metrikler) genişletilecek."""
import numpy as np
import pandas as pd

TRADING_DAYS = 252


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
