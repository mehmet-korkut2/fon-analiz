"""Walk-forward değerlendirmenin bütün sonuçlarını JSON'a çevrilebilir bir sözlük olarak üretir.

scripts/ml_degerlendir.py bunu markdown'a, gece işi (app/ml/job.py) `ml_reports` tablosuna yazar;
/model-performansi sayfası oradan okur.

Takvim ve başarı ölçütü sonuçlar görülmeden önce belirlendi (docs/ml_tahmin.md):
- Ayar dönemi 10.2023 - 09.2024 (LightGBM hiperparametreleri sadece burada seçildi: BEST_PARAMS)
- Test dönemi 10.2024 - 09.2026 (24 ay)
- Model bir risk grubunda, o grubun en iyi referansına göre hem daha düşük fazla getiri MAE'si hem
  daha yüksek "ilk 10" getirisi sağlarsa başarılı sayılır.
"""
from __future__ import annotations

import itertools
import math
from datetime import date, datetime

import numpy as np
import pandas as pd

from app.ml import evaluation as E
from app.ml.features import HORIZON, RISK_GROUPS
from app.ml.models import BASELINES, BEST_PARAMS, Arima, Drift, LightGBM, LightGBMRank, select_arima_order

VALID = (pd.Timestamp("2023-10-01"), pd.Timestamp("2024-09-30"))
TEST = (pd.Timestamp("2024-10-01"), pd.Timestamp("2026-09-30"))
GRID = {"num_leaves": [7, 15, 31], "min_child_samples": [100, 400], "n_estimators": [150, 400]}
ARIMA_PER_GROUP = 10
SEED = 42
GROUP_LABELS = {"1-2": "Risk 1-2", "3-4": "Risk 3-4", "5-7": "Risk 5-7", "bilinmiyor": "Risk değeri yok"}
LABELS = {m.name: m.label for m in [*BASELINES, LightGBM(), LightGBMRank()]} | {"arima": "ARIMA (fon bazında)"}


def _clean(v):
    """JSON için: NaN/inf -> None, numpy -> python."""
    if isinstance(v, (np.floating, float)):
        return None if math.isnan(v) or math.isinf(v) else float(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return v.strftime("%Y-%m-%d")
    return v


def records(df: pd.DataFrame) -> list[dict]:
    out = []
    for r in df.to_dict("records"):
        r = {k: _clean(v) for k, v in r.items()}
        if "model" in r:
            r["label"] = LABELS.get(r["model"], r["model"])
        out.append(r)
    return out


def split_origins(data: pd.DataFrame) -> tuple[list, list]:
    origins = sorted(data["date"].unique())
    valid = [pd.Timestamp(t) for t in origins if VALID[0] <= t <= VALID[1]]
    test = [pd.Timestamp(t) for t in origins if TEST[0] <= t <= TEST[1]]
    return valid, test


def tune(data: pd.DataFrame, valid: list) -> tuple[dict, list[dict]]:
    rows = []
    for values in itertools.product(*GRID.values()):
        params = dict(zip(GRID, values))
        p = E.walk_forward(data, valid, LightGBM(**params))
        rows.append({**params, "mae_excess": E.monthly(p)["mae_excess"].mean()})
    res = pd.DataFrame(rows).sort_values("mae_excess")
    best = {k: int(v) for k, v in res.iloc[0][list(GRID)].items()}
    return best, records(res)


def drift_interval(data: pd.DataFrame, valid: list, test: list) -> dict:
    """Sitede gösterilen tahmin (drift) için ham getiri ölçeğinde %80 aralık, risk grubuna göre.
    q10/q90: bütün gerçekleşmiş drift hataları (her tahmin anında yalnızca o güne kadar bilinenler
    kullanılır; burada en son durum). coverage: test döneminde, her ay sadece geçmiş hatalarla kurulan
    aralığın gerçekleşmeyi içerme oranı."""
    hist = E.walk_forward(data, valid, Drift())
    pt = E.add_intervals(E.walk_forward(data, test, Drift()), hist, scale="raw")
    allp = E.walk_forward(data, sorted(data["date"].unique()), Drift())
    resid = allp["y"] - allp["pred_raw"]
    out = {}
    for g in RISK_GROUPS:
        r = resid[allp["risk_group"] == g]
        sub = pt[pt["risk_group"] == g]
        out[g] = {"q10": _clean(r.quantile(E.INTERVAL[0])), "q90": _clean(r.quantile(E.INTERVAL[1])),
                  "n": int(len(r)), "coverage": _clean(E.coverage(sub, "raw")), "test_n": int(sub["lo"].notna().sum())}
    return out


def arima_section(panel, data: pd.DataFrame, test: list, preds: pd.DataFrame) -> dict:
    eligible = data[data["date"].isin(test)].groupby("code")["date"].nunique()
    full = set(eligible.index[eligible == len(test)])
    first = data[(data["date"] == test[0]) & data["code"].isin(full)]
    rng = np.random.default_rng(SEED)
    sample = []
    for g in RISK_GROUPS:
        codes = sorted(first.loc[first["risk_group"] == g, "code"])
        sample += list(rng.choice(codes, size=min(ARIMA_PER_GROUP, len(codes)), replace=False))
    pre = panel.prices.index[panel.prices.index < test[0]][-1]  # mertebe: test verisi görülmeden
    orders = {c: select_arima_order(panel, c, pre) for c in sample}
    ar = E.walk_forward(data[data["code"].isin(sample)], test, Arima(panel, orders, HORIZON))
    same = preds[preds["code"].isin(sample) & preds["model"].isin([m.name for m in BASELINES] + ["lightgbm"])]
    rows = E.summarize(pd.concat([same, ar]), by_group=False).sort_values("mae_excess").drop(columns=["top10", "coverage"], errors="ignore")
    oc = pd.Series([f"({p},0,{q})" for p, _, q in orders.values()]).value_counts()
    return {"funds": len(sample), "rows": records(rows), "orders": {k: int(v) for k, v in oc.items()}}


def build_report(panel, data: pd.DataFrame, *, do_tune: bool = False, arima: bool = False, explore: bool = True,
                 log=lambda m: None) -> dict:
    valid, test = split_origins(data)
    params, tuning = (tune(data, valid) if do_tune else (dict(BEST_PARAMS), None))
    log(f"parametreler: {params}")

    models = [*BASELINES, LightGBM(**params)]
    hist = {m.name: E.walk_forward(data, valid, m) for m in models}
    preds = pd.concat([E.add_intervals(E.walk_forward(data, test, m), hist[m.name]) for m in models], ignore_index=True)
    log("test tahminleri bitti")

    overall = E.summarize(preds, by_group=False).sort_values("mae_excess")
    by = E.summarize(preds, by_group=True)
    monthly = E.monthly(preds)
    bench = monthly.groupby("date")[["universe", "mm"]].first().mean()

    verdicts, groups = [], {}
    for g in RISK_GROUPS:
        sub = by[by["risk_group"] == g].sort_values("mae_excess")
        if sub.empty:
            continue
        groups[g] = records(sub)
        ref = sub[sub["model"] != "lightgbm"].iloc[0]
        lg = sub[sub["model"] == "lightgbm"].iloc[0]
        h = E.head_to_head(preds, "lightgbm", ref["model"], group=g)
        ok_mae = bool(lg["mae_excess"] < ref["mae_excess"])
        ok_top = bool(lg["top10"] > ref["top10"]) if not pd.isna(ref["top10"]) else True
        verdicts.append({"group": g, "group_label": GROUP_LABELS[g], "n": int(lg["n"]), "reference": ref["model"],
                         "reference_label": LABELS[ref["model"]], "model_mae_excess": _clean(lg["mae_excess"]),
                         "reference_mae_excess": _clean(ref["mae_excess"]), "model_top10": _clean(lg["top10"]),
                         "reference_top10": _clean(ref["top10"]), "wins": h["wins"], "months": h["months"],
                         "mean_diff": _clean(h["mean_diff"]), "se": _clean(h["se"]), "success": ok_mae and ok_top})

    final = LightGBM(**params).fit(E.train_rows(data, test[-1]))
    imp = final.importance().rename_axis("feature").reset_index(name="share")

    report = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data_as_of": _clean(panel.prices.index[-1]),
        "horizon": HORIZON,
        "calendar": {
            "origins": int(data["date"].nunique()), "first": _clean(min(data["date"])), "last": _clean(max(data["date"])),
            "samples": int(len(data)), "funds": int(data["code"].nunique()),
            "valid": [_clean(valid[0]), _clean(valid[-1]), len(valid)], "test": [_clean(test[0]), _clean(test[-1]), len(test)],
            "test_samples": int(data["date"].isin(test).sum()),
        },
        "params": params, "tuning": tuning,
        "overall": records(overall),
        "benchmarks": {"universe": _clean(bench["universe"]), "mm": _clean(bench["mm"])},
        "groups": groups, "verdicts": verdicts,
        "monthly": records(monthly),
        "importance": records(imp),
        "drift_interval": drift_interval(data, valid, test),
        "arima": None, "exploration": None,
    }
    log("ana sonuçlar bitti")

    if explore:
        rank = LightGBMRank(**params)
        rp = E.add_intervals(E.walk_forward(data, test, rank), E.walk_forward(data, valid, LightGBMRank(**params)))
        both = pd.concat([preds[preds["model"].isin(["drift", "lightgbm", "momentum"])], rp], ignore_index=True)
        ex_by = E.summarize(both, by_group=True)
        fr = LightGBMRank(**params).fit(E.train_rows(data, test[-1]))
        report["exploration"] = {
            "overall": records(E.summarize(both, by_group=False).sort_values("ic", ascending=False)),
            "groups": {g: records(ex_by[ex_by["risk_group"] == g].sort_values("ic", ascending=False)) for g in RISK_GROUPS
                       if (ex_by["risk_group"] == g).any()},
            "monthly": records(E.monthly(rp)),
            "importance": records(fr.importance().rename_axis("feature").reset_index(name="share")),
        }
        log("keşif varyantı bitti")

    if arima:
        report["arima"] = arima_section(panel, data, test, preds)
        log("ARIMA bitti")
    return report
