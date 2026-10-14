"""Tahmin modelleri. Her model `predict(train, test)` ile test satırları için ham ve fazla getiri
tahmini döndürür (sütunlar: pred_raw, pred_excess; index test'inkiyle aynı).

- Referans modeller ham getiriyi tahmin eder; fazla getiri = ham - t'deki PP seviyesi tahmini (mm_level).
- ML modelleri fazla getiriyi öğrenir; ham tahmin = mm_level + fazla getiri tahmini. Faiz seviyesi
  bütün fonları birlikte kaydırır ve fon özelliklerinden öngörülemez; onu drift ile ayrı tahmin edip
  modeli fonlar arasındaki farka odaklamak bu yüzden.
"""
from __future__ import annotations

import pandas as pd


class Model:
    name: str = ""
    label: str = ""
    needs_training = False

    def predict(self, train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError


class RawBaseline(Model):
    """Ham getiriyi doğrudan veren basit referans."""

    def raw(self, test: pd.DataFrame) -> pd.Series:
        raise NotImplementedError

    def predict(self, train, test):
        raw = self.raw(test).astype(float)
        return pd.DataFrame({"pred_raw": raw, "pred_excess": raw - test["mm_level"]}, index=test.index)


class Zero(RawBaseline):
    name, label = "sifir", "Sıfır getiri"

    def raw(self, test):
        return pd.Series(0.0, index=test.index)


class Drift(RawBaseline):
    name, label = "drift", "Drift (son 1 yılın aylık ortalaması)"

    def raw(self, test):
        return test["drift"]


class Momentum(RawBaseline):
    name, label = "momentum", "Momentum (son 1 ay devam eder)"

    def raw(self, test):
        return test["ret_1m"]


BASELINES = [Zero(), Drift(), Momentum()]


# --- LightGBM: tüm fonlarda ortak, fazla getiriyi öğrenir ---------------------------------

LGBM_DEFAULTS = dict(
    objective="l1", n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=200,
    subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=42, verbose=-1,
)
TARGET_CLIP = (0.005, 0.995)  # eğitimde hedefin uç değerleri kırpılır (ör. SPK kapanışındaki -%99)


class LightGBM(Model):
    name, label = "lightgbm", "LightGBM (tüm fonlarda ortak)"
    needs_training = True

    def __init__(self, **params):
        self.params = {**LGBM_DEFAULTS, **params}
        self.booster = None

    def fit(self, train: pd.DataFrame) -> "LightGBM":
        # LightGBM'in kendi arayüzü (lgb.train): sklearn arayüzü scikit-learn bağımlılığı istiyor
        import lightgbm as lgb

        from app.ml.features import CATEGORICAL, FEATURES

        y = train["y_excess"]
        lo, hi = y.quantile(TARGET_CLIP[0]), y.quantile(TARGET_CLIP[1])
        p = dict(self.params)
        rounds = p.pop("n_estimators")
        ds = lgb.Dataset(train[FEATURES], y.clip(lo, hi), categorical_feature=CATEGORICAL, free_raw_data=False)
        self.booster = lgb.train(p, ds, num_boost_round=rounds)
        return self

    def predict_excess(self, test: pd.DataFrame) -> pd.Series:
        from app.ml.features import FEATURES

        return pd.Series(self.booster.predict(test[FEATURES]), index=test.index)

    def predict(self, train, test):
        self.fit(train)
        ex = self.predict_excess(test)
        return pd.DataFrame({"pred_raw": test["mm_level"] + ex, "pred_excess": ex}, index=test.index)

    def importance(self) -> pd.Series:
        from app.ml.features import FEATURES

        imp = self.booster.feature_importance(importance_type="gain")
        return pd.Series(imp, index=FEATURES).sort_values(ascending=False) / imp.sum()


# --- ARIMA: fon bazında, günlük log getiriler üzerinde ------------------------------------

ARIMA_ORDERS = [(p, 0, q) for p in range(3) for q in range(3)]
ARIMA_WINDOW = 504  # son ~2 yıl


def _log_returns(panel, code: str, t: pd.Timestamp):
    import numpy as np

    pos = panel.prices.index.get_loc(t)
    s = panel.filled[code].iloc[max(0, pos - ARIMA_WINDOW): pos + 1].dropna()
    s.iloc[-1] = panel.raw_filled[code].iloc[pos]  # t'nin kendisi: temizlenmemiş fiyat (sızıntı yok)
    return np.log(s).diff().dropna().to_numpy()


def _fit_arima(r, order):
    import warnings

    from statsmodels.tsa.arima.model import ARIMA

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ARIMA(r, order=order, trend="c").fit()


def select_arima_order(panel, code: str, t: pd.Timestamp) -> tuple[int, int, int]:
    """t'ye kadarki veriyle AIC'si en düşük (p, 0, q)."""
    r = _log_returns(panel, code, t)
    best, best_aic = (0, 0, 0), float("inf")
    for order in ARIMA_ORDERS:
        try:
            aic = _fit_arima(r, order).aic
        except Exception:  # yakınsamayan mertebe atlanır
            continue
        if aic < best_aic:
            best, best_aic = order, aic
    return best


def arima_forecast(panel, code: str, t: pd.Timestamp, order, horizon: int) -> float:
    """21 adımlık günlük log getiri tahminlerinin toplamı -> ham getiri."""
    import numpy as np

    r = _log_returns(panel, code, t)
    try:
        f = _fit_arima(r, order).forecast(horizon)
    except Exception:
        f = np.full(horizon, r.mean())  # yakınsamazsa drift
    return float(np.exp(np.sum(f)) - 1)


class Arima(Model):
    """Fon bazında ARIMA. Mertebe her fon için ilk test ayından önce bir kez seçilir (`orders`)."""
    name, label = "arima", "ARIMA (fon bazında)"

    def __init__(self, panel, orders: dict[str, tuple], horizon: int = 21):
        self.panel, self.orders, self.horizon = panel, orders, horizon

    def predict(self, train, test):
        raw = pd.Series([arima_forecast(self.panel, c, t, self.orders[c], self.horizon)
                         for c, t in zip(test["code"], test["date"])], index=test.index)
        return pd.DataFrame({"pred_raw": raw, "pred_excess": raw - test["mm_level"]}, index=test.index)
