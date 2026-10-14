import numpy as np
import pandas as pd
import pytest

from app.ml import evaluation as E
from app.ml.features import HORIZON, build_dataset, features_at, make_panel, month_starts, target_at
from app.ml.models import BASELINES, Drift, Momentum, Zero

IDX = pd.bdate_range("2023-01-02", "2025-06-30")


def synthetic_panel(seed=0):
    rng = np.random.default_rng(seed)
    n = len(IDX)
    cols = {
        "MM1": 1.0 * 1.0015 ** np.arange(n),
        "MM2": 1.0 * 1.0014 ** np.arange(n),
        "MM3": 1.0 * 1.0016 ** np.arange(n),
        "EQ1": 1.0 * np.cumprod(1 + rng.normal(0.001, 0.015, n)),
        "EQ2": 1.0 * np.cumprod(1 + rng.normal(0.0005, 0.02, n)),
        "YNG": np.r_[np.full(n - 100, np.nan), 1.0 * 1.001 ** np.arange(100)],  # yeni fon: geçmişi yok
    }
    prices = pd.DataFrame(cols, index=IDX)
    meta = pd.DataFrame({
        "category": ["Para Piyasası"] * 3 + ["Hisse Senedi", "Hisse Senedi", "Değişken"],
        "risk_level": [1, 1, 1, 6, 7, None],
    }, index=list(cols))
    return make_panel(prices, meta)


def test_month_starts_need_history_and_horizon():
    panel = synthetic_panel()
    starts = month_starts(panel)
    assert all(d.day <= 7 for d in starts)
    assert all(panel.prices.index.get_loc(d) >= 252 for d in starts)
    assert all(panel.prices.index.get_loc(d) + HORIZON < len(IDX) for d in starts)
    assert starts[0] == pd.Timestamp("2024-01-01") and starts[-1] == pd.Timestamp("2025-05-01")


def test_features_do_not_see_the_future():
    panel = synthetic_panel()
    t = pd.Timestamp("2024-06-03")
    before = features_at(panel, t)
    # t'den sonraki bütün fiyatları (t+1 dahil) değiştir: t'deki özellikler aynı kalmalı
    future = synthetic_panel().prices.copy()
    future.loc[future.index > t] *= 3
    future.loc[future.index > t, "EQ1"] = 0.01  # t+1'de "hatalı fiyat" gibi görünen sıçramalar dahil
    after = features_at(make_panel(future, synthetic_panel().meta.assign(category=lambda m: m["category"].astype(str))), t)
    pd.testing.assert_frame_equal(before.drop(columns="category"), after.drop(columns="category"))
    assert "YNG" not in before.index  # 1 yıllık geçmişi yok
    assert before.loc["EQ1", "ret_1m"] == pytest.approx(panel.prices.loc[t, "EQ1"] / panel.prices["EQ1"].iloc[panel.prices.index.get_loc(t) - 21] - 1)
    assert before["mm_ret_12m"].nunique() == 1 and before.loc["MM1", "rank_ret_1m"] <= 1


def test_target_and_excess():
    panel = synthetic_panel()
    t = pd.Timestamp("2024-06-03")
    pos = IDX.get_loc(t)
    y, end = target_at(panel, t, ["EQ1", "MM1"])
    assert end == IDX[pos + HORIZON]
    assert y["EQ1"] == pytest.approx(panel.prices["EQ1"].iloc[pos + HORIZON] / panel.prices["EQ1"].iloc[pos] - 1)
    data = build_dataset(panel, [t])
    mm = data.loc[data["code"].str.startswith("MM"), "y"].median()
    assert data["y_excess"].tolist() == pytest.approx((data["y"] - mm).tolist())
    assert target_at(panel, IDX[-5], ["EQ1"]) is None  # 21 gün sonrası yok


def test_train_rows_only_use_finished_targets():
    panel = synthetic_panel()
    data = build_dataset(panel, month_starts(panel))
    aug = data[data["date"] == pd.Timestamp("2024-08-01")]
    end = aug["end"].iloc[0]  # 1 Ağustos + 21 işlem günü = 30 Ağustos
    assert end == pd.Timestamp("2024-08-30")
    # t, örneğin hedefinin bittiği gün: örnek henüz eğitimde kullanılamaz (gerçekleşmesi t'de biliniyor ama
    # t'deki tahmin anında değil); bir gün sonra kullanılabilir
    assert pd.Timestamp("2024-08-01") not in set(E.train_rows(data, end)["date"])
    train = E.train_rows(data, end + pd.Timedelta(days=1))
    assert pd.Timestamp("2024-08-01") in set(train["date"]) and (train["end"] <= end).all()


def test_baselines_and_walk_forward():
    panel = synthetic_panel()
    data = build_dataset(panel, month_starts(panel))
    origins = sorted(data["date"].unique())[-6:]
    preds = pd.concat([E.walk_forward(data, origins, m) for m in BASELINES])
    assert set(preds["model"]) == {"sifir", "drift", "momentum"}
    d = preds[preds["model"] == "drift"].set_index(["date", "code"])
    src = data.set_index(["date", "code"])
    assert d["pred_raw"].tolist() == pytest.approx(src.loc[d.index, "drift"].tolist())
    assert d["pred_excess"].tolist() == pytest.approx((src.loc[d.index, "drift"] - src.loc[d.index, "mm_level"]).tolist())
    assert (preds[preds["model"] == "sifir"]["pred_raw"] == 0).all()
    assert isinstance(Zero(), type(BASELINES[0])) and Drift().name == "drift" and Momentum().name == "momentum"


def test_metrics_on_known_values():
    t1, t2 = pd.Timestamp("2025-01-01"), pd.Timestamp("2025-02-03")
    preds = pd.DataFrame({
        "model": "m", "date": [t1] * 3 + [t2] * 3, "end": [t2] * 3 + [t2 + pd.Timedelta(days=30)] * 3,
        "code": list("ABCABC"), "risk_group": ["1-2", "5-7", "5-7"] * 2,
        "y": [0.02, 0.10, -0.05, 0.03, -0.02, 0.04], "mm_y": [0.03] * 3 + [0.025] * 3,
        "pred_raw": [0.03, 0.05, 0.00, 0.03, 0.01, 0.02],
    })
    preds["y_excess"] = preds["y"] - preds["mm_y"]
    preds["mm_level"] = 0.03
    preds["pred_excess"] = preds["pred_raw"] - preds["mm_level"]
    s = E.summarize(preds, by_group=False).iloc[0]
    assert s["mae"] == pytest.approx(np.mean([0.01, 0.05, 0.05, 0.0, 0.03, 0.02]))
    assert s["rmse"] == pytest.approx(np.sqrt(np.mean(np.square([0.01, 0.05, 0.05, 0.0, 0.03, 0.02]))))
    # ham işaret: 0.00 tahmini (işaret 0) negatif getiriyle uyuşmaz
    assert s["dir_raw"] == pytest.approx(4 / 6)
    assert s["top10"] == pytest.approx(np.mean([np.mean([0.02, 0.10, -0.05]), np.mean([0.03, -0.02, 0.04])]))
    m = E.monthly(preds)
    assert list(m["universe"]) == pytest.approx([np.mean([0.02, 0.10, -0.05]), np.mean([0.03, -0.02, 0.04])])
    h = E.head_to_head(pd.concat([preds, preds.assign(model="ref", pred_excess=preds["pred_excess"] + 0.01)]), "m", "ref")
    assert h["months"] == 2


def test_conformal_intervals_use_only_past_errors():
    panel = synthetic_panel()
    data = build_dataset(panel, month_starts(panel))
    origins = sorted(data["date"].unique())
    preds = E.walk_forward(data, origins, Drift())
    iv = E.add_intervals(preds, min_n=3)
    first = iv[iv["date"] == origins[0]]
    assert first["lo"].isna().all()  # ilk ayda bilinen geçmiş hata yok
    later = iv[iv["date"] == origins[-1]]
    assert later["lo"].notna().all() and (later["lo"] <= later["pred_excess"]).all() and (later["hi"] >= later["pred_excess"]).all()


def test_lightgbm_walk_forward_does_not_see_test_targets():
    from app.ml.models import LightGBM

    panel = synthetic_panel()
    data = build_dataset(panel, month_starts(panel))
    origins = sorted(data["date"].unique())[-3:]
    params = dict(n_estimators=20, min_child_samples=5, num_leaves=4)
    a = E.walk_forward(data, origins, LightGBM(**params))
    # t'de henüz bilinmeyen bütün gerçekleşmeler (hedefi t'de ya da sonra biten satırlar, t'nin kendi
    # satırları dahil) bozulduğunda t'deki tahmin aynı kalmalı
    t = origins[-1]
    tampered = data.copy()
    unknown = tampered["end"] >= t
    tampered.loc[unknown, ["y", "y_excess"]] = 99.0
    b = E.walk_forward(tampered, [t], LightGBM(**params))
    assert a.loc[a["date"] == t, "pred_excess"].tolist() == pytest.approx(b["pred_excess"].tolist())
    # bilinen bir gerçekleşme değişirse (hedefi t'den önce biten satır) tahmin değişebilir: test anlamlı
    known = tampered.copy()
    known.loc[known["end"] < t, "y_excess"] *= -1
    c_ = E.walk_forward(known, [t], LightGBM(**params))
    assert c_["pred_excess"].tolist() != pytest.approx(b["pred_excess"].tolist())
    assert a["pred_raw"].tolist() == pytest.approx((a["mm_level"] + a["pred_excess"]).tolist())
    # aynı tohum: aynı sonuç
    c = E.walk_forward(data, origins, LightGBM(**params))
    assert a["pred_excess"].tolist() == pytest.approx(c["pred_excess"].tolist())
    m = LightGBM(**params).fit(E.train_rows(data, origins[-1]))
    assert m.importance().sum() == pytest.approx(1)


def test_arima_order_and_forecast():
    from app.ml.models import ARIMA_ORDERS, arima_forecast, select_arima_order

    panel = synthetic_panel()
    t = pd.Timestamp("2025-03-03")
    order = select_arima_order(panel, "EQ1", t)
    assert order in ARIMA_ORDERS
    f = arima_forecast(panel, "EQ1", t, order, HORIZON)
    assert np.isfinite(f) and -0.5 < f < 0.5
    # düzgün büyüyen PP fonu: tahmin, günlük büyümenin 21 günlük karşılığına yakın
    mm = arima_forecast(panel, "MM1", t, (0, 0, 0), HORIZON)
    assert mm == pytest.approx(1.0015 ** HORIZON - 1, rel=0.05)
