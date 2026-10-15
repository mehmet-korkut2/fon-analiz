"""Teknik göstergeler: hareketli ortalamalar, 200 günlük ortalamaya göre trend, 52 haftalık aralık.

Göstergeler geçmiş fiyat hareketini özetler, tahmin değildir (ML değerlendirmesinde momentum ve
1 yıllık zirveye uzaklık gibi fiyat özellikleri drift'i geçemedi, docs/ml_tahmin.md).
Hesaptan önce tek günlük hatalı fiyatlar çıkarılır (metriklerle aynı, drop_one_day_glitches).
Ortalamalar işlem günü sayısıyla (gözlem sayısı) alınır; pencere dolmadan değer üretilmez.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.services.data_quality import drop_one_day_glitches

MA_WINDOWS = (50, 200)
RANGE_DAYS = 364  # 52 hafta
# 200 işlem günü ≈ 290 takvim günü; tatiller için pay bırakılır
WARMUP_DAYS = 320


def moving_averages(prices: pd.Series, windows=MA_WINDOWS) -> pd.DataFrame:
    """Tarih indeksli fiyat serisinden her pencere için basit hareketli ortalama (ma50, ma200...)."""
    return pd.DataFrame({f"ma{w}": prices.rolling(w, min_periods=w).mean() for w in windows})


def range_52w(prices: pd.Series) -> dict:
    """Son 52 haftanın en yüksek/en düşük fiyatı ve son fiyatın bu aralıktaki yeri (0 = dip, 1 = zirve)."""
    last_date = prices.index[-1]
    window = prices[prices.index > last_date - timedelta(days=RANGE_DAYS)]
    high, low, last = float(window.max()), float(window.min()), float(prices.iloc[-1])
    return {
        "high": high,
        "high_date": window.idxmax(),
        "low": low,
        "low_date": window.idxmin(),
        "position": (last - low) / (high - low) if high > low else None,
        # Fon 52 haftadan yeniyse aralık kısa dönemi kapsar; arayüz bunu belirtir
        "full": bool(prices.index[0] <= last_date - timedelta(days=RANGE_DAYS)),
        "since": window.index[0],
    }


def summarize(prices: pd.Series) -> dict:
    """Son güne ait özet: fiyat, ortalamalar, trend (200 günlüğün üstü/altı) ve 52 haftalık aralık."""
    ma = moving_averages(prices).iloc[-1]
    last = float(prices.iloc[-1])
    ma200 = None if pd.isna(ma["ma200"]) else float(ma["ma200"])
    trend = None if ma200 is None else ("ustunde" if last > ma200 else "altinda" if last < ma200 else "esit")
    return {
        "as_of": prices.index[-1],
        "price": last,
        "ma50": None if pd.isna(ma["ma50"]) else float(ma["ma50"]),
        "ma200": ma200,
        "trend": trend,
        "range_52w": range_52w(prices),
    }


def technical(rows: list[tuple[date, float]], since: date) -> dict | None:
    """DB satırlarından (tarih, fiyat) özet ve since'ten itibaren günlük ortalama serisi.

    rows, ortalamaların ısınması için since'ten en az WARMUP_DAYS önce başlamalıdır.
    """
    if not rows:
        return None
    s = pd.Series([p for _, p in rows], index=[d for d, _ in rows], dtype=float).sort_index()
    s = drop_one_day_glitches(s)
    ma = moving_averages(s)
    ma = ma[ma.index >= since]
    series = [
        {"date": d, "ma50": None if pd.isna(r.ma50) else float(r.ma50), "ma200": None if pd.isna(r.ma200) else float(r.ma200)}
        for d, r in ma.iterrows()
    ]
    return {"summary": summarize(s), "series": series}
