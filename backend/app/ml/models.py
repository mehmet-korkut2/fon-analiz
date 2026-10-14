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
