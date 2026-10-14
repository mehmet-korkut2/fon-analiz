"""Fiyat paneli, tahmin başlangıç günleri, özellikler ve hedef.

Sızıntı kuralları:
- t günündeki özellikler yalnızca t ve öncesindeki fiyatlardan hesaplanır (`features_at`).
- Hedef: t'den 21 işlem günü sonraki getiri. Eğitimde yalnızca hedef penceresi t'den ÖNCE biten
  örnekler kullanılır (`end` < t; bkz. evaluation.train_rows).
- Para piyasası (PP) seviyesi de t'deki bilgiyle hesaplanır; gerçekleşen PP medyanı sadece
  değerlendirmede (fazla getiriyi ölçmek için) kullanılır.
- Tek günlük hatalı fiyat temizliği (drop_one_day_glitches) bir günün hatalı olduğuna ertesi güne
  bakarak karar verir; bu yüzden t gününün kendi fiyatı için temizlenmemiş fiyat kullanılır (t+1'i
  görmeden). Önceki günlerin "ertesi günü" en geç t olduğundan onlar için sorun yok.
- Kategori ve risk değeri için elimizde sadece bugünkü değerler var (bilinen küçük sızıntı).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fund, Price
from app.services.data_quality import drop_one_day_glitches
from app.services.metrics_job import RISK_FREE_CATEGORY, STALE_AFTER_DAYS

HORIZON = 21  # işlem günü (~1 ay)
YEAR = 252
MIN_HISTORY = 200  # son 252 işlem gününde en az bu kadar fiyat (~1 yıllık geçmiş)

FEATURES = [
    "ret_1m", "ret_3m", "ret_6m", "ret_12m",
    "vol_3m", "vol_12m", "mdd_12m", "dist_high_12m",
    "rank_ret_1m", "rank_ret_12m",
    "risk_level", "category",
    "mm_ret_1m", "mm_ret_12m",
]
CATEGORICAL = ["category"]
RISK_GROUPS = ["1-2", "3-4", "5-7", "bilinmiyor"]


@dataclass
class Panel:
    prices: pd.DataFrame  # satır işlem günü, sütun fon; tek günlük hatalar çıkarılmış, boşluklar NaN
    filled: pd.DataFrame  # ileri doldurulmuş (verisi kesilen fon son fiyatında kalır)
    raw_filled: pd.DataFrame  # temizlenmemiş fiyatlar, ileri doldurulmuş (t gününün kendi fiyatı için)
    meta: pd.DataFrame  # index fon: category (kategorik), risk_level
    mm_codes: list[str]


def make_panel(prices: pd.DataFrame, meta: pd.DataFrame, raw: pd.DataFrame | None = None) -> Panel:
    """`prices`: tek günlük hataları çıkarılmış geniş tablo; `raw`: temizlenmemiş hali (yoksa aynısı)."""
    meta = meta.copy()
    meta["category"] = pd.Categorical(meta["category"].fillna("Bilinmiyor"))
    prices = prices.sort_index()
    raw = prices if raw is None else raw.reindex(index=prices.index, columns=prices.columns)
    mm = [c for c in meta.index[meta["category"] == RISK_FREE_CATEGORY] if c in prices.columns]
    return Panel(prices, prices.ffill(), raw.ffill(), meta, mm)


def load_panel(db: Session) -> Panel:
    rows = db.execute(select(Price.fund_code, Price.date, Price.price)).all()
    df = pd.DataFrame(rows, columns=["code", "date", "price"])
    df["date"] = pd.to_datetime(df["date"])
    raw = df.pivot_table(index="date", columns="code", values="price", aggfunc="last")
    series = {c: drop_one_day_glitches(g.sort_values("date").set_index("date")["price"]) for c, g in df.groupby("code")}
    prices = pd.DataFrame(series)
    meta = pd.DataFrame(db.execute(select(Fund.code, Fund.category, Fund.risk_level)).all(),
                        columns=["code", "category", "risk_level"]).set_index("code")
    return make_panel(prices, meta, raw)


def risk_group(level) -> str:
    if level is None or pd.isna(level):
        return "bilinmiyor"
    return "1-2" if level <= 2 else "3-4" if level <= 4 else "5-7"


def month_starts(panel: Panel, horizon: int = HORIZON) -> list[pd.Timestamp]:
    """Her ayın ilk işlem günü; en az 1 yıllık geçmişi ve (değerlendirme için) 21 işlem günü sonrası olanlar."""
    idx = panel.prices.index
    firsts = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).first()
    last_ok = idx[-1 - horizon] if len(idx) > horizon else idx[0]
    return [pd.Timestamp(d) for d in firsts if d.day <= 7 and idx.get_loc(d) >= YEAR and d <= last_ok]


def _ret(hist: pd.DataFrame, k: int) -> pd.Series:
    return hist.iloc[-1] / hist.iloc[-1 - k] - 1


def features_at(panel: Panel, t: pd.Timestamp) -> pd.DataFrame:
    """t günündeki özellikler (index fon). Sadece t'ye kadarki fiyatlar kullanılır."""
    pos = panel.prices.index.get_loc(t)
    raw = panel.prices.iloc[: pos + 1]
    hist = panel.filled.iloc[: pos + 1].iloc[-(YEAR + 1):]
    # aday: t'de güncel fiyatı olan ve ~1 yıllık geçmişi olan fonlar
    last_seen = raw.apply(lambda s: s.last_valid_index())
    fresh = last_seen.notna() & (last_seen >= t - pd.Timedelta(days=STALE_AFTER_DAYS))
    enough = raw.iloc[-YEAR:].notna().sum() >= MIN_HISTORY
    codes = fresh.index[fresh & enough & hist.iloc[0].notna()]
    h = hist[codes].copy()
    h.iloc[-1] = panel.raw_filled[codes].iloc[pos]  # t'nin kendisi: temizlenmemiş fiyat (t+1'e bakmadan)
    daily = h.pct_change(fill_method=None)
    f = pd.DataFrame(index=codes)
    f["ret_1m"], f["ret_3m"], f["ret_6m"], f["ret_12m"] = _ret(h, 21), _ret(h, 63), _ret(h, 126), _ret(h, YEAR)
    f["vol_3m"] = daily.iloc[-63:].std() * np.sqrt(YEAR)
    f["vol_12m"] = daily.std() * np.sqrt(YEAR)
    f["mdd_12m"] = (h / h.cummax() - 1).min()
    f["dist_high_12m"] = h.iloc[-1] / h.max() - 1
    f["rank_ret_1m"] = f["ret_1m"].rank(pct=True)
    f["rank_ret_12m"] = f["ret_12m"].rank(pct=True)
    f["risk_level"] = panel.meta["risk_level"].reindex(codes).astype(float)
    f["category"] = panel.meta["category"].reindex(codes)
    mm = f.loc[f.index.isin(panel.mm_codes)]
    f["mm_ret_1m"] = mm["ret_1m"].median() if len(mm) else np.nan
    f["mm_ret_12m"] = mm["ret_12m"].median() if len(mm) else np.nan
    # PP seviyesinin t'deki tahmini (drift): son 1 yılın aylığa çevrilmiş hali
    f["mm_level"] = (1 + f["mm_ret_12m"]) ** (HORIZON / YEAR) - 1
    f["drift"] = (1 + f["ret_12m"]) ** (HORIZON / YEAR) - 1
    f["risk_group"] = f["risk_level"].map(risk_group)
    return f


def target_at(panel: Panel, t: pd.Timestamp, codes, horizon: int = HORIZON) -> tuple[pd.Series, pd.Timestamp] | None:
    """t'den `horizon` işlem günü sonraki getiri. Verisi dönemde kesilen fon son fiyatında kalır."""
    pos = panel.prices.index.get_loc(t)
    if pos + horizon >= len(panel.prices.index):
        return None
    f = panel.filled[list(codes)]
    y = f.iloc[pos + horizon] / f.iloc[pos] - 1
    return y, panel.prices.index[pos + horizon]


def build_dataset(panel: Panel, origins: list[pd.Timestamp]) -> pd.DataFrame:
    """Her başlangıç günü için özellikler + hedef (ham ve PP medyanına göre fazla getiri)."""
    parts = []
    for t in origins:
        f = features_at(panel, t)
        if f.empty:
            continue
        tgt = target_at(panel, t, f.index)
        if tgt is None:
            continue
        y, end = tgt
        f = f.assign(date=t, end=end, y=y)
        mm_y = f.loc[f.index.isin(panel.mm_codes), "y"].median()
        f["mm_y"] = mm_y  # gerçekleşen PP medyanı (sadece değerlendirme ve fazla getiri hedefi için)
        f["y_excess"] = f["y"] - mm_y
        parts.append(f.rename_axis("code").reset_index())
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    df["category"] = pd.Categorical(df["category"], categories=panel.meta["category"].cat.categories)
    return df
