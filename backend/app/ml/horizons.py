"""Gün gün tahmin (tahmin karnesi): her fon için 1..21 işlem günü ufkunda drift tahmini ve her ufka ayrı
kalibre edilmiş konformal %80 aralık.

Tahmin: h günlük ufukta (1 + son 1 yıllık getiri)^(h/252) - 1 (features.features_at'teki drift'in her ufka
genellenmiş hali; h = 21'de aynısı).

Konformal aralık (ufuk h, risk grubu g, tahmin günü t): drift'in geçmiş hatalarının (gerçekleşen h günlük
getiri - tahmin) %10 ve %90 dilimleri tahmine eklenir. Hatalar bütün işlem günlerinden başlatılan tahminlerden
gelir; yalnızca hedef günü t'den ÖNCE gelmiş olanlar kullanılır (başlangıç satırı + h < t). Grupta 50'den az
hata varsa bütün grupların hataları kullanılır (evaluation.add_intervals ile aynı kural).

Sızıntı önlemleri (features.py'deki kurallara ek):
- t'deki uygunluk (fiyatı güncel mi, son 1 yılda en az 200 fiyatı var mı) t günü için temizlenmemiş fiyatın
  varlığına bakar. Temizlenmiş fiyat t'nin hatalı olup olmadığına t+1'e bakarak karar verir; features_at bu
  küçük farkı içerir, burada yok.
- Hata ve gerçekleşen değer temizlenmemiş fiyatlardan hesaplanır (karnede kullanıcının gördüğü fiyat).

Gerçekleşen: tahmin gününden sonraki h'inci işlem günündeki fiyat (fon o gün fiyat yayınlamadıysa önceki son
fiyatı; verisi kesilen fon son fiyatında kalır, features.target_at ile aynı).

Sapma yüzdesi her yerde (gerçekleşen - tahmin) / tahmin.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.ml.evaluation import INTERVAL
from app.ml.features import HORIZON, MIN_HISTORY, RISK_GROUPS, YEAR, Panel, risk_group
from app.ml.trading_calendar import target_dates
from app.models import SOURCE_BACKFILL, SOURCE_LIVE, ForecastDay, ForecastSummary, Fund, Price
from app.services.fund_status import STATUS_ACTIVE
from app.services.metrics_job import STALE_AFTER_DAYS

HORIZONS = list(range(1, HORIZON + 1))
SUMMARY_HORIZONS = [1, 2, 5, 10, 21]
HORIZON_LABELS = {1: "1 gün", 2: "2 gün", 5: "1 hafta", 10: "2 hafta", 21: "1 ay"}
MIN_N = 50  # bir risk grubunda aralık için en az bu kadar geçmiş hata
BACKFILL_DAYS = 60  # geriye dönük hesaplanan işlem günü sayısı
METHOD = "drift-konformal"
METHOD_VERSION = "v1"
# Kayıtlar yapıldıkları sürümle saklanır; yöntem değişirse yeni sürüm eklenir, eski kayıtlar değişmez.
METHOD_VERSIONS = {
    "v0": "21 günlük drift; %80 aralık yalnızca ayın ilk işlem günü başlatılan tahminlerin hatalarıyla, "
          "risk grubuna göre (karneden önceki yöntem, 22.10.2026 kayıtları)",
    "v1": "1-21 işlem günü drift; %80 aralık her ufuk ve risk grubu için ayrı, her işlem günü başlatılan "
          "tahminlerin hedef günü gelmiş hatalarıyla; resmi tatil takvimi",
}
ALL = "tumu"


def _f(v) -> float | None:
    if v is None:
        return None
    v = float(v)
    return None if math.isnan(v) or math.isinf(v) else v


class DriftPanel:
    """Bütün işlem günleri x fonlar için drift tahmini, uygunluk ve gerçekleşen getiri (vektörel)."""

    def __init__(self, panel: Panel):
        P = panel.prices
        idx = P.index
        self.dates = idx
        self.codes = P.columns
        T, N = P.shape
        self.R = panel.raw_filled.reindex(index=idx, columns=self.codes).to_numpy(dtype=float)
        F = panel.filled.to_numpy(dtype=float)
        clean = P.notna().to_numpy()
        seen = (panel.raw_seen if panel.raw_seen is not None else P.notna()).reindex(
            index=idx, columns=self.codes, fill_value=False).to_numpy(dtype=bool)
        rows = np.arange(T)
        # son 252 işlem günündeki fiyat sayısı: t-251..t-1 temizlenmiş, t günü ham fiyat (t+1'e bakmadan)
        cs = np.vstack([np.zeros((1, N)), np.cumsum(clean, axis=0)])
        cnt = cs[rows] - cs[np.maximum(rows - (YEAR - 1), 0)] + seen
        # son fiyat günü: t'de ham fiyat varsa t, yoksa t-1'e kadarki son temizlenmiş fiyat
        last_clean = np.maximum.accumulate(np.where(clean, rows[:, None], -1), axis=0)
        prev = np.vstack([np.full((1, N), -1), last_clean[:-1]])
        last = np.where(seen, rows[:, None], prev)
        last_date = idx.values[np.clip(last, 0, None)]
        limit = (idx - pd.Timedelta(days=STALE_AFTER_DAYS)).values[:, None]
        fresh = (last >= 0) & (last_date >= limit)
        start = np.full((T, N), np.nan)
        if T > YEAR:
            start[YEAR:] = F[:-YEAR]
        self.eligible = fresh & (cnt >= MIN_HISTORY) & ~np.isnan(start) & ~np.isnan(self.R)
        with np.errstate(invalid="ignore", divide="ignore"):
            self.ret12 = np.where(self.eligible, self.R / start - 1, np.nan)
        levels = panel.meta["risk_level"].reindex(self.codes)
        self.groups = np.array([risk_group(v) for v in levels])

    def pos(self, d) -> int:
        return int(self.dates.get_loc(pd.Timestamp(d)))

    def pred(self, h: int) -> np.ndarray:
        with np.errstate(invalid="ignore"):
            return np.power(1 + self.ret12, h / YEAR) - 1

    def realized(self, h: int) -> np.ndarray:
        """t satırında: t'den h işlem günü sonraki fiyat / t'deki fiyat - 1 (yoksa NaN)."""
        out = np.full(self.R.shape, np.nan)
        if len(self.dates) > h:
            with np.errstate(invalid="ignore", divide="ignore"):
                out[:-h] = self.R[h:] / self.R[:-h] - 1
        return out

    def resid(self, h: int) -> np.ndarray:
        r = self.realized(h) - self.pred(h)
        r[~self.eligible] = np.nan
        return r


class Calibrator:
    """Tek ufuk için geçmiş hatalar, başlangıç gününe göre sıralı (her risk grubu ve tümü)."""

    def __init__(self, dp: DriftPanel, h: int, resid: np.ndarray | None = None):
        self.h = h
        r = dp.resid(h) if resid is None else resid
        self.pools = {}
        for g in [*RISK_GROUPS, ALL]:
            sub = r if g == ALL else r[:, dp.groups == g]
            ok = ~np.isnan(sub)
            rows, _ = np.nonzero(ok)  # satır sırasıyla: başlangıç günü artan
            self.pools[g] = (rows, sub[ok])

    def known(self, g: str, c: int) -> np.ndarray:
        """c günündeki tahmin için kullanılabilecek hatalar: hedef günü c'den önce (satır + h < c)."""
        rows, vals = self.pools[g]
        return vals[: np.searchsorted(rows, c - self.h, side="left")]

    def at(self, c: int) -> dict[str, tuple[float, float, int] | None]:
        out = {}
        for g in RISK_GROUPS:
            v = self.known(g, c)
            if len(v) < MIN_N:
                v = self.known(ALL, c)
            if len(v) < MIN_N:
                out[g] = None
                continue
            q10, q90 = np.quantile(v, INTERVAL)
            out[g] = (float(q10), float(q90), int(len(v)))
        return out


# --- değerlendirme (rapor) ------------------------------------------------------------------------

def evaluate(dp: DriftPanel, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Test dönemindeki her işlem günü x fon x ufuk için aralığın kapsaması ve sapma. Hız için kalibrasyon
    ayda bir yenilenir: ayın ilk işlem gününde, hedef günü o günden önce gelmiş hatalarla kurulur ve ay
    boyunca kullanılır (sızıntı yok: kalibrasyon günü <= tahmin günü)."""
    rows_all = np.arange(len(dp.dates))
    in_test = (dp.dates >= start) & (dp.dates <= end)
    test_rows = rows_all[in_test]
    if len(test_rows) == 0:
        return {}
    months = pd.Series(test_rows, index=dp.dates[in_test]).groupby([dp.dates[in_test].year, dp.dates[in_test].month])
    out, current = [], []
    for h in HORIZONS:
        r = dp.resid(h)
        p = dp.pred(h)
        cal = Calibrator(dp, h, r)
        acc = {g: np.zeros(5) for g in [*RISK_GROUPS, ALL]}  # n, kapsanan, |sapma|, sapma, genişlik
        for _, mrows in months:
            mrows = mrows.to_numpy()
            q = cal.at(int(mrows[0]))
            for g in RISK_GROUPS:
                if q[g] is None:
                    continue
                q10, q90, _ = q[g]
                cols = dp.groups == g
                rr, pp = r[np.ix_(mrows, cols)], p[np.ix_(mrows, cols)]
                ok = ~np.isnan(rr)
                if not ok.any():
                    continue
                rr, pp = rr[ok], pp[ok]
                err = rr / (1 + pp)
                v = np.array([len(rr), ((rr >= q10) & (rr <= q90)).sum(), np.abs(err).sum(), err.sum(),
                              ((q90 - q10) / (1 + pp)).sum()])
                acc[g] += v
                acc[ALL] += v
        for g, (n, cov, ae, e, w) in acc.items():
            if n:
                out.append({"horizon": h, "group": g, "n": int(n), "coverage": cov / n, "mae_pct": ae / n,
                            "bias_pct": e / n, "width_pct": w / n})
        q = cal.at(len(dp.dates) - 1)  # bugünkü aralık (son tahmin gününde kullanılan)
        for g in RISK_GROUPS:
            if q[g]:
                current.append({"horizon": h, "group": g, "q10": q[g][0], "q90": q[g][1], "n": q[g][2]})
    return {"test": [str(dp.dates[test_rows[0]].date()), str(dp.dates[test_rows[-1]].date())],
            "origins": int(len(test_rows)), "calibration": "monthly", "rows": out, "current": current}


# --- kayıt (gece işi) -----------------------------------------------------------------------------

def closed_codes(db: Session) -> set[str]:
    return set(db.scalars(select(Fund.code).where(Fund.status.is_not(None), Fund.status != STATUS_ACTIVE)))


def forecast_rows(dp: DriftPanel, cals: dict[int, Calibrator], c: int, source: str, exclude: set[str]) -> list[dict]:
    """c günü için bütün uygun fonların 1..21 günlük tahmin kayıtları."""
    as_of = dp.dates[c].date()
    known_days = [d.date() for d in dp.dates[c + 1: c + 1 + HORIZON]]
    targets = target_dates(as_of, HORIZON, known_days)
    qs = {h: cals[h].at(c) for h in HORIZONS}
    rows = []
    for j in np.nonzero(dp.eligible[c])[0]:
        code = dp.codes[j]
        if code in exclude:
            continue
        g, base, r12 = dp.groups[j], float(dp.R[c, j]), float(dp.ret12[c, j])
        for h in HORIZONS:
            q = qs[h][g]
            if q is None:
                continue
            pred = (1 + r12) ** (h / YEAR) - 1
            rows.append({"fund_code": code, "as_of": as_of, "base_price": base, "horizon": h,
                         "target_date": targets[h - 1], "pred_price": base * (1 + pred),
                         "lo_price": base * (1 + pred + q[0]), "hi_price": base * (1 + pred + q[1]),
                         "method": METHOD, "method_version": METHOD_VERSION, "source": source, "risk_group": g,
                         "calib_n": q[2]})
    return rows


def _has(db: Session, as_of: date, source: str, horizon: int | None = None) -> bool:
    q = select(ForecastDay.id).where(ForecastDay.as_of == as_of, ForecastDay.source == source)
    if horizon is not None:
        q = q.where(ForecastDay.horizon == horizon)
    return db.scalars(q.limit(1)).first() is not None


def store(db: Session, dp: DriftPanel, backfill_days: int = BACKFILL_DAYS) -> dict:
    """Son fiyat günü için canlı tahmin (o gün için zaten varsa dokunulmaz) ve son `backfill_days` işlem
    gününden tahmini olmayanlar için geriye dönük tahmin. Mevcut kayıtlar silinmez, değiştirilmez."""
    T = len(dp.dates)
    if T == 0:
        return {"live": 0, "backfill": 0, "backfill_days": 0}
    cals = {h: Calibrator(dp, h) for h in HORIZONS}
    exclude = closed_codes(db)
    live = 0
    last = dp.dates[-1].date()
    if not _has(db, last, SOURCE_LIVE, 1):
        rows = forecast_rows(dp, cals, T - 1, SOURCE_LIVE, exclude)
        if rows:
            db.execute(insert(ForecastDay), rows)
        live = len(rows)
    back, days = 0, 0
    for c in range(max(T - 1 - backfill_days, 0), T - 1):
        d = dp.dates[c].date()
        # tam canlı kaydı (1 günlük ufuk dahil) ya da geriye dönük kaydı olan gün atlanır
        if _has(db, d, SOURCE_LIVE, 1) or _has(db, d, SOURCE_BACKFILL):
            continue
        rows = forecast_rows(dp, cals, c, SOURCE_BACKFILL, exclude)
        if rows:
            db.execute(insert(ForecastDay), rows)
            back += len(rows)
            days += 1
    db.commit()
    return {"live": live, "backfill": back, "backfill_days": days}


# --- karne: gerçekleşenle karşılaştırma -----------------------------------------------------------

def realize(df: pd.DataFrame, market_days: pd.DatetimeIndex, price_at) -> pd.DataFrame:
    """`df`: as_of, horizon, pred_price, lo_price, hi_price (+ fund_code). `market_days`: fiyat verisindeki
    işlem günleri. `price_at(codes, dates)`: o gün ya da öncesindeki son fiyat. Ekler: realized_date,
    realized_price, error_tl, error_pct, in_band (henüz gelmemişse NaN/None)."""
    df = df.copy()
    pos = market_days.get_indexer(pd.to_datetime(df["as_of"])) + df["horizon"].to_numpy()
    ok = (pos >= df["horizon"].to_numpy()) & (pos < len(market_days))
    df["realized_date"] = pd.NaT
    df.loc[ok, "realized_date"] = market_days[pos[ok]]
    df["realized_price"] = np.nan
    if ok.any():
        df.loc[ok, "realized_price"] = price_at(df.loc[ok, "fund_code"].to_numpy(), df.loc[ok, "realized_date"].to_numpy())
    df["error_tl"] = df["realized_price"] - df["pred_price"]
    df["error_pct"] = df["realized_price"] / df["pred_price"] - 1
    real = df["realized_price"].notna()
    df["in_band"] = None
    df.loc[real, "in_band"] = (df.loc[real, "realized_price"] >= df.loc[real, "lo_price"]) & \
        (df.loc[real, "realized_price"] <= df.loc[real, "hi_price"])
    return df


def score(df: pd.DataFrame, keys: list[str]) -> list[dict]:
    """Gerçekleşmiş kayıtlarda kapsama ve ortalama sapma (realize çıktısı)."""
    r = df[df["realized_price"].notna()]
    out = []
    for k, g in r.groupby(keys):
        k = k if isinstance(k, tuple) else (k,)
        out.append({**{key: v.item() if isinstance(v, np.generic) else v for key, v in zip(keys, k)}, "n": int(len(g)), "days": int(g["as_of"].nunique()),
                    "coverage": _f(g["in_band"].astype(bool).mean()), "mae_pct": _f(g["error_pct"].abs().mean()),
                    "bias_pct": _f(g["error_pct"].mean())})
    return out


def panel_price_at(dp: DriftPanel):
    col = {c: j for j, c in enumerate(dp.codes)}

    def price_at(codes, dates):
        rows = dp.dates.get_indexer(pd.to_datetime(dates))
        cols = np.array([col.get(c, -1) for c in codes])
        out = np.full(len(codes), np.nan)
        ok = (rows >= 0) & (cols >= 0)
        out[ok] = dp.R[rows[ok], cols[ok]]
        return out

    return price_at


def summarize_all(db: Session, dp: DriftPanel) -> dict:
    """Bütün fonların karnesi: kaynak x ufuk x risk grubu (ve tümü). Gece işinde hesaplanıp saklanır."""
    cols = [ForecastDay.fund_code, ForecastDay.as_of, ForecastDay.horizon, ForecastDay.pred_price,
            ForecastDay.lo_price, ForecastDay.hi_price, ForecastDay.source, ForecastDay.method_version, ForecastDay.risk_group]
    df = pd.DataFrame(db.execute(select(*cols)).all(), columns=[c.key for c in cols])
    payload = {"data_as_of": str(dp.dates[-1].date()) if len(dp.dates) else None, "rows": [], "counts": {}}
    if df.empty:
        return payload
    r = realize(df, dp.dates, panel_price_at(dp))
    payload["rows"] = score(r, ["source", "method_version", "horizon", "risk_group"]) + \
        [{**x, "risk_group": ALL} for x in score(r, ["source", "method_version", "horizon"])]
    payload["versions"] = METHOD_VERSIONS
    payload["counts"] = {s: {"records": int((df["source"] == s).sum()), "days": int(df.loc[df["source"] == s, "as_of"].nunique()),
                             "first": str(df.loc[df["source"] == s, "as_of"].min()) if (df["source"] == s).any() else None,
                             "realized": int(r.loc[r["source"] == s, "realized_price"].notna().sum())}
                         for s in (SOURCE_LIVE, SOURCE_BACKFILL)}
    return payload


def save_summary(db: Session, payload: dict) -> None:
    db.execute(delete(ForecastSummary))
    db.add(ForecastSummary(data_as_of=date.fromisoformat(payload["data_as_of"]), payload=payload))
    db.commit()


def latest_summary(db: Session) -> ForecastSummary | None:
    return db.scalars(select(ForecastSummary).order_by(ForecastSummary.id.desc()).limit(1)).first()


# --- tek fonun karnesi (API) ----------------------------------------------------------------------

@dataclass
class MonthForecast:
    """Fon detayındaki 1 aylık tahmin kartı ve portföy planlayıcı için: son tahmin gününün 21 günlük kaydı
    (ham getiri)."""
    fund_code: str
    as_of: date
    source: str
    method: str
    method_version: str
    risk_group: str
    pred_return: float
    lo: float
    hi: float
    calib_n: int | None
    path: list[dict]


def latest_forecasts(db: Session, codes: list[str] | None = None) -> dict[str, MonthForecast]:
    """Her fonun en son tahmin günündeki 1..21 günlük tahmini (aynı gün canlı varsa canlı)."""
    q = select(ForecastDay).where(ForecastDay.as_of == select(ForecastDay.as_of).order_by(ForecastDay.as_of.desc()).limit(1).scalar_subquery())
    if codes is not None:
        q = q.where(ForecastDay.fund_code.in_(codes))
    rows = sorted(db.scalars(q), key=lambda x: (x.fund_code, x.source != SOURCE_LIVE, x.horizon))
    out: dict[str, MonthForecast] = {}
    by: dict[str, list[ForecastDay]] = {}
    for x in rows:
        lst = by.setdefault(x.fund_code, [])
        if lst and lst[0].source != x.source:
            continue  # canlı varken geriye dönüğü alma
        lst.append(x)
    for code, lst in by.items():
        m = next((x for x in lst if x.horizon == HORIZON), None)
        if m is None:
            continue
        out[code] = MonthForecast(
            fund_code=code, as_of=m.as_of, source=m.source, method=m.method, method_version=m.method_version,
            risk_group=m.risk_group,
            pred_return=m.pred_price / m.base_price - 1, lo=m.lo_price / m.base_price - 1, hi=m.hi_price / m.base_price - 1,
            calib_n=m.calib_n,
            path=[{"horizon": x.horizon, "target_date": x.target_date, "pred_return": x.pred_price / x.base_price - 1,
                   "lo": x.lo_price / x.base_price - 1, "hi": x.hi_price / x.base_price - 1} for x in lst])
    return out


def fund_scorecard(db: Session, code: str, as_of: date | None = None, source: str | None = None,
                   max_days: int = 30) -> dict | None:
    """Bir fonun tahmin karnesi: son `max_days` tahmin günü, seçilen günün gün gün tablosu ve ufuk özeti
    (fonun bütün kayıtları üzerinden, canlı ve geriye dönük ayrı)."""
    cols = [ForecastDay.as_of, ForecastDay.horizon, ForecastDay.target_date, ForecastDay.base_price, ForecastDay.pred_price,
            ForecastDay.lo_price, ForecastDay.hi_price, ForecastDay.source, ForecastDay.method, ForecastDay.method_version,
            ForecastDay.risk_group, ForecastDay.calib_n]
    df = pd.DataFrame(db.execute(select(*cols).where(ForecastDay.fund_code == code)).all(), columns=[c.key for c in cols])
    if df.empty:
        return None
    df["fund_code"] = code
    first = df["as_of"].min()
    market = pd.DatetimeIndex(sorted(pd.to_datetime(db.scalars(select(Price.date).where(Price.date >= first).distinct()).all())))
    ps = pd.DataFrame(db.execute(select(Price.date, Price.price).where(Price.fund_code == code, Price.date >= first)).all(),
                      columns=["date", "price"])
    series = pd.Series(ps["price"].to_numpy(), index=pd.to_datetime(ps["date"])).sort_index().reindex(market).ffill()

    def price_at(_codes, dates):
        return series.reindex(pd.to_datetime(dates)).to_numpy()

    r = realize(df, market, price_at)
    days = (r.groupby(["as_of", "source"])
            .agg(realized=("realized_price", lambda s: int(s.notna().sum())), horizons=("horizon", "count"),
                 version=("method_version", "first"), method=("method", "first"))
            .reset_index().sort_values(["as_of", "source"], ascending=[False, True]).head(max_days))
    day_list = [{"as_of": d.as_of, "source": d.source, "horizons": int(d.horizons), "realized": int(d.realized),
                 "method": d.method, "method_version": d.version} for d in days.itertuples()]
    if as_of is None:
        # varsayılan: bütün günleri gerçekleşmiş en yeni tahmin (grafik baştan sona dolu); yoksa en çok gerçekleşen
        pick = next((d for d in day_list if d["realized"] == d["horizons"] and d["realized"] > 0), None) or \
            max(day_list, key=lambda d: d["realized"])
        as_of, source = pick["as_of"], pick["source"]
    elif source is None:
        source = SOURCE_LIVE if ((r["as_of"] == as_of) & (r["source"] == SOURCE_LIVE)).any() else SOURCE_BACKFILL
    sel = r[(r["as_of"] == as_of) & (r["source"] == source)].sort_values("horizon")
    selected = None
    if not sel.empty:
        s0 = sel.iloc[0]
        selected = {
            "as_of": as_of, "source": source, "method": s0["method"], "method_version": s0["method_version"],
            "method_note": METHOD_VERSIONS.get(s0["method_version"]), "risk_group": s0["risk_group"],
            "base_price": float(s0["base_price"]),
            "rows": [{"horizon": int(x.horizon), "target_date": x.target_date,
                      "realized_date": x.realized_date.date() if pd.notna(x.realized_date) else None,
                      "pred_price": float(x.pred_price), "lo_price": float(x.lo_price), "hi_price": float(x.hi_price),
                      "realized_price": _f(x.realized_price), "error_tl": _f(x.error_tl), "error_pct": _f(x.error_pct),
                      "in_band": None if x.in_band is None else bool(x.in_band), "calib_n": x.calib_n}
                     for x in sel.itertuples()],
        }
    summ = score(r[r["horizon"].isin(SUMMARY_HORIZONS)], ["source", "method_version", "horizon"])
    for x in summ:
        x["label"] = HORIZON_LABELS[x["horizon"]]
    return {"code": code, "data_as_of": market[-1].date() if len(market) else None, "days": day_list,
            "selected": selected, "summary": summ}
