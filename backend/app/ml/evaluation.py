"""Walk-forward değerlendirme ve metrikler.

Her test başlangıcı t için model, hedef penceresi t'den önce biten örneklerle (genişleyen pencere)
yeniden eğitilir ve t'deki fonlar için tahmin yapar. Böylece hiçbir tahmin, kendi gerçekleşmesinden
ya da t'den sonraki bir fiyattan bilgi almaz.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.features import RISK_GROUPS
from app.ml.models import Model

TOP_N = 10
INTERVAL = (0.10, 0.90)  # %80 aralık


def train_rows(data: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """t'de eğitimde kullanılabilecek örnekler: hedef penceresi t'den ÖNCE bitmiş olanlar."""
    return data[data["end"] < t]


def walk_forward(data: pd.DataFrame, origins: list[pd.Timestamp], model: Model) -> pd.DataFrame:
    out = []
    for t in origins:
        test = data[data["date"] == t]
        if test.empty:
            continue
        train = train_rows(data, t)
        if model.needs_training and train.empty:
            continue
        p = model.predict(train, test)
        out.append(test[["date", "end", "code", "risk_group", "y", "y_excess", "mm_y", "mm_level"]].join(p).assign(model=model.name))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def add_intervals(preds: pd.DataFrame, history: pd.DataFrame | None = None, q=INTERVAL, min_n: int = 50) -> pd.DataFrame:
    """Konformal aralık: t'deki tahminin etrafına, t'den ÖNCE gerçekleşmiş (hedef penceresi t'den önce
    biten) tahmin hatalarının risk grubuna göre %10 ve %90 dilimleri eklenir. `history`: aynı modelin
    ayar dönemindeki tahminleri (ilk test aylarında yeterli hata birikmesi için)."""
    preds = preds.copy()
    preds["lo"] = np.nan
    preds["hi"] = np.nan
    pool = pd.concat([history, preds]) if history is not None else preds
    pool = pool.assign(resid=pool["y_excess"] - pool["pred_excess"])
    for t in preds["date"].unique():
        known = pool[pool["end"] < t]  # bir tahminin hatası, hedef penceresi bittikten sonra bilinir
        for g in RISK_GROUPS:
            r = known.loc[known["risk_group"] == g, "resid"]
            if len(r) < min_n:
                r = known["resid"]
            if len(r) < min_n:
                continue
            lo, hi = r.quantile(q[0]), r.quantile(q[1])
            m = (preds["date"] == t) & (preds["risk_group"] == g)
            preds.loc[m, "lo"] = preds.loc[m, "pred_excess"] + lo
            preds.loc[m, "hi"] = preds.loc[m, "pred_excess"] + hi
    return preds


def _top(g: pd.DataFrame, n: int = TOP_N) -> float:
    if g["pred_raw"].nunique() <= 1:  # sabit tahmin (ör. sıfır): sıralama anlamsız
        return np.nan
    return g.nlargest(n, "pred_raw")["y"].mean()


def _ic(g: pd.DataFrame) -> float:
    """Ay içi sıralama korelasyonu (Spearman): tahmin edilen ve gerçekleşen fazla getiri."""
    if g["pred_excess"].nunique() <= 1:
        return np.nan
    return g["pred_excess"].rank().corr(g["y_excess"].rank())


def monthly(preds: pd.DataFrame) -> pd.DataFrame:
    """Model x ay: hata, sıralama, ilk 10'un gerçekleşen getirisi, tüm fonların ortalaması, PP medyanı."""
    rows = []
    for (model, t), g in preds.groupby(["model", "date"]):
        rows.append({
            "model": model, "date": t, "n": len(g),
            "mae_excess": (g["y_excess"] - g["pred_excess"]).abs().mean(),
            "ic": _ic(g), "top10": _top(g), "universe": g["y"].mean(), "mm": g["mm_y"].iloc[0],
        })
    return pd.DataFrame(rows)


def summarize(preds: pd.DataFrame, by_group: bool = True) -> pd.DataFrame:
    """Model (ve risk grubu) bazında: MAE, RMSE (ham ve fazla), yön doğruluğu (ham işaret ve PP medyanının
    üstü/altı), ortalama aylık sıralama korelasyonu, ilk 10'un ortalama gerçekleşen getirisi, aralık kapsamı."""
    keys = ["model", "risk_group"] if by_group else ["model"]
    rows = []
    for k, g in preds.groupby(keys):
        k = k if isinstance(k, tuple) else (k,)
        e, ex = g["y"] - g["pred_raw"], g["y_excess"] - g["pred_excess"]
        row = dict(zip(keys, k))
        row.update(
            n=len(g), months=g["date"].nunique(),
            mae=e.abs().mean(), rmse=np.sqrt((e ** 2).mean()),
            mae_excess=ex.abs().mean(), rmse_excess=np.sqrt((ex ** 2).mean()),
            dir_raw=(np.sign(g["pred_raw"]) == np.sign(g["y"])).mean(),
            dir_excess=((g["pred_excess"] > 0) == (g["y_excess"] > 0)).mean(),
            ic=g.groupby("date").apply(_ic, include_groups=False).mean(),
        )
        # ilk 10: her ay tahmini en yüksek 10 fon (grup bazında: grubun içinden)
        row["top10"] = g.groupby("date").apply(_top, include_groups=False).mean()
        if "lo" in g and g["lo"].notna().any():
            m = g["lo"].notna()
            row["coverage"] = ((g.loc[m, "y_excess"] >= g.loc[m, "lo"]) & (g.loc[m, "y_excess"] <= g.loc[m, "hi"])).mean()
        rows.append(row)
    return pd.DataFrame(rows)


def head_to_head(preds: pd.DataFrame, model: str, reference: str, group: str | None = None) -> dict:
    """Model ile referansın aylık fazla getiri MAE'si: kaç ayda model daha iyi, ortalama fark ve standart hatası."""
    p = preds if group is None else preds[preds["risk_group"] == group]
    m = monthly(p)
    a = m[m["model"] == model].set_index("date")["mae_excess"]
    b = m[m["model"] == reference].set_index("date")["mae_excess"]
    d = (a - b).dropna()  # negatif: model daha iyi
    return {"months": len(d), "wins": int((d < 0).sum()), "mean_diff": float(d.mean()) if len(d) else np.nan,
            "se": float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else np.nan}
