"""Risk profiline göre fon önerisi, örnek portföy ve geriye dönük test.

Akış (ayrıntılar ve gerekçeler: docs/oneri_sistemi.md):
1. Aday havuzu: aktif, güncel verili, SPK kararıyla kapatılmamış, 1 yıllık getirisi ve
   volatilitesi olan fonlar.
2. Profil süzgeci: TEFAS risk değeri profilin aralığında, ölçülen volatilite profilin sınırının
   altında; risk değeri boş fonlar ve (nitelikli yatırımcı değilse) serbest fonlar dışarıda.
3. Dört bileşen, profilin havuzu içinde yüzdelik dilime çevrilir (1 = en iyi) ve profile özgü
   ağırlıklarla toplanır.
4. Puan sırasıyla seçilir, aynı kategoriden en fazla 2 fon alınır.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import BacktestWindow, Fund, FundMetrics, Price
from app.services.data_quality import drop_one_day_glitches
from app.services.fund_status import is_tradable
from app.services.metrics import MIN_VOL_FOR_SHARPE, compute_fund_metrics
from app.services.metrics_job import RISK_FREE_CATEGORY, STALE_AFTER_DAYS
from app.services.risk_survey import AGRESIF, DENGELI, PROFILE_LABELS, PROFILE_RULES, TEMKINLI

COMPONENTS = ("getiri", "riske_gore", "dusus", "tutarlilik")
COMPONENT_LABELS = {
    "getiri": "Fazla getiri",
    "riske_gore": "Riske göre getiri",
    "dusus": "Düşüş direnci",
    "tutarlilik": "Tutarlılık",
}

# Ağırlıkların gerekçesi docs/oneri_sistemi.md'de
WEIGHTS = {
    TEMKINLI: {"getiri": 0.15, "riske_gore": 0.25, "dusus": 0.35, "tutarlilik": 0.25},
    DENGELI: {"getiri": 0.20, "riske_gore": 0.35, "dusus": 0.25, "tutarlilik": 0.20},
    AGRESIF: {"getiri": 0.35, "riske_gore": 0.30, "dusus": 0.15, "tutarlilik": 0.20},
}

# Sharpe'ı olmayan (volatilitesi %5 altı) fonların "riske göre getiri" puanı:
# - "ayri": fazla getirileri sadece düşük volatiliteli fonlar arasında yüzdeliğe çevrilir; en iyi
#   para piyasası fonu da 1'e yakın puan alır. Temkinli profilin havuzu çoğunlukla bu fonlardan
#   oluştuğu için orada bunlar birbirleriyle yarışmalı.
# - "tum": fazla getirileri tüm havuzun fazla getirileri içinde yüzdeliğe çevrilir; riskli
#   fonların arasında bir para piyasası fonu ancak getirisi gerçekten yüksekse öne çıkar.
RA_MODE = {TEMKINLI: "ayri", DENGELI: "tum", AGRESIF: "tum"}

CATEGORY_LIMIT = 2

# Dengeli profilde önerilerin ve örnek portföyün en az bu kadarı "riskli" gruptan gelir: TEFAS risk
# değeri 4+ ve volatilitesi %5+ (yani gerçekten dalgalanan) fonlar. Yüksek faiz dönemlerinde riske
# göre getiri ölçütleri dengeli profili tamamen para piyasası benzeri fonlara yönlendiriyordu
# (docs/oneri_sistemi.md, 6.1).
RISKY_QUOTA = {DENGELI: 2}
RISKY_MIN_LEVEL = 4
PORTFOLIO_SIZE = {TEMKINLI: 3, DENGELI: 4, AGRESIF: 5}
SERBEST_CATEGORY = "Serbest"
BACKTEST_MONTHS = 12

FRAME_COLUMNS = ["code", "name", "category", "risk_level", "ret_3m", "ret_6m", "ret_1y", "vol", "sharpe", "mdd", "as_of"]


# --- Aday havuzu --------------------------------------------------------------

def current_candidates(db: Session) -> tuple[pd.DataFrame, date | None]:
    """Bugünkü metriklerle aday havuzu (profil süzgecinden önce)."""
    latest = db.scalar(select(func.max(FundMetrics.as_of)))
    if latest is None:
        return pd.DataFrame(columns=FRAME_COLUMNS), None
    cutoff = latest - timedelta(days=STALE_AFTER_DAYS)
    rows = db.execute(
        select(Fund.code, Fund.name, Fund.category, Fund.risk_level, FundMetrics.ret_3m, FundMetrics.ret_6m,
               FundMetrics.ret_1y, FundMetrics.volatility_1y, FundMetrics.sharpe_1y, FundMetrics.max_drawdown_1y,
               FundMetrics.as_of)
        .join(FundMetrics)
        .where(Fund.is_active.is_(True), is_tradable(), FundMetrics.as_of >= cutoff,
               FundMetrics.ret_1y.is_not(None), FundMetrics.volatility_1y.is_not(None))
    ).all()
    return pd.DataFrame(rows, columns=FRAME_COLUMNS), latest


def risk_free_from(df: pd.DataFrame) -> float | None:
    rets = df.loc[df["category"] == RISK_FREE_CATEGORY, "ret_1y"].dropna()
    return statistics.median(rets) if len(rets) else None


def eligible(df: pd.DataFrame, profile: str, qualified: bool) -> pd.DataFrame:
    rule = PROFILE_RULES[profile]
    lo, hi = rule.risk_range
    out = df[df["risk_level"].notna() & df["risk_level"].between(lo, hi)]
    if rule.max_volatility is not None:
        out = out[out["vol"] <= rule.max_volatility]
    if not qualified:
        out = out[out["category"] != SERBEST_CATEGORY]
    return out.copy()


# --- Puanlama -----------------------------------------------------------------

def _pct(s: pd.Series) -> pd.Series:
    """Yüzdelik dilim, büyük değer iyi: en iyi 1, en kötü 1/n."""
    return s.rank(pct=True, method="average")


def _annualize(r: pd.Series, years: float) -> pd.Series:
    return (1 + r) ** (1 / years) - 1


def score(pool: pd.DataFrame, profile: str, rf: float, ra_mode: str | None = None,
          weights: dict[str, float] | None = None) -> pd.DataFrame:
    """Havuzdaki her fona bileşen yüzdelikleri ve toplam puan ekler, puana göre sıralar."""
    ra_mode = ra_mode or RA_MODE[profile]
    weights = weights or WEIGHTS[profile]
    df = pool.copy()
    if df.empty:
        return df.assign(**{c: pd.Series(dtype=float) for c in (*COMPONENTS, "score")})

    df["excess"] = df["ret_1y"] - rf
    periods = pd.DataFrame({
        "3 ay": _annualize(df["ret_3m"], 0.25),
        "6 ay": _annualize(df["ret_6m"], 0.5),
        "12 ay": df["ret_1y"],
    })
    df["worst_ann"] = periods.min(axis=1, skipna=True)
    df["worst_period"] = periods.idxmin(axis=1, skipna=True)
    df["low_vol"] = df["vol"] < MIN_VOL_FOR_SHARPE

    df["getiri"] = _pct(df["excess"])
    ra = pd.Series(index=df.index, dtype=float)
    hi = ~df["low_vol"] & df["sharpe"].notna()
    ra[hi] = _pct(df.loc[hi, "sharpe"])
    lo = ~hi
    ra[lo] = _pct(df.loc[lo, "excess"]) if ra_mode == "ayri" else df.loc[lo, "getiri"]
    df["riske_gore"] = ra
    df["dusus"] = _pct(df["mdd"].fillna(0))
    df["tutarlilik"] = _pct(df["worst_ann"] - rf)
    df["score"] = sum(df[c] * w for c, w in weights.items())
    return df.sort_values(["score", "code"], ascending=[False, True])


def is_risky(df: pd.DataFrame) -> pd.Series:
    return (df["risk_level"] >= RISKY_MIN_LEVEL) & (df["vol"] >= MIN_VOL_FOR_SHARPE)


def _by_score(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(["score", "code"], ascending=[False, True])


def diversify(scored: pd.DataFrame, limit: int, category_limit: int = CATEGORY_LIMIT, min_risky: int = 0) -> pd.DataFrame:
    """Puan sırasıyla seçer; aynı kategoriden en fazla `category_limit` fon. `min_risky` > 0 ise
    önce en yüksek puanlı riskli fonlar (is_risky) alınır, kalan yerler puan sırasıyla dolar."""
    picked, per_cat = [], {}

    def take(rows, upto):
        for idx, row in rows.iterrows():
            if len(picked) >= upto:
                return
            cat = row["category"] or "-"
            if idx in picked or per_cat.get(cat, 0) >= category_limit:
                continue
            picked.append(idx)
            per_cat[cat] = per_cat.get(cat, 0) + 1

    if min_risky:
        take(scored[is_risky(scored)], min(min_risky, limit))
    take(scored, limit)
    return _by_score(scored.loc[picked])


def portfolio_pick(recs: pd.DataFrame, size: int, min_risky: int = 0) -> pd.DataFrame:
    """Önerilerden örnek portföy: (varsa kota kadar riskli fon), sonra her kategoriden en iyisi,
    yetmezse kalan en iyiler."""
    picked: list = []
    if min_risky:
        risky = recs[is_risky(recs)]
        picked += list(risky.drop_duplicates("category").index[:min_risky])
        picked += [i for i in risky.index if i not in picked][: min_risky - len(picked)]
    used = set(recs.loc[picked, "category"])
    for idx, row in recs.iterrows():
        if len(picked) >= size:
            break
        if idx not in picked and row["category"] not in used:
            picked.append(idx)
            used.add(row["category"])
    picked += [i for i in recs.index if i not in picked][: size - len(picked)]
    return _by_score(recs.loc[picked])


# --- Gerekçe metinleri --------------------------------------------------------

def _num(v: float, digits: int = 1) -> str:
    return f"{v:.{digits}f}".replace(".", ",")


def _p(v: float, digits: int = 1) -> str:
    """Yüzde, işaretsiz: 0.052 -> '%5,2'."""
    return "%" + _num(abs(v) * 100, digits)


def _bucket(p: float) -> str:
    if p >= 0.9:
        return "adayların ilk %10'unda"
    if p >= 0.75:
        return "adayların ilk %25'inde"
    if p >= 0.5:
        return "adayların üst yarısında"
    return "adayların alt yarısında"


def _vs_rf(row) -> str:
    side = "üstünde" if row["excess"] >= 0 else "altında"
    return f"risksiz getirinin {_num(abs(row['excess']) * 100)} puan {side}"


def _strength(row, comp: str, rf: float) -> str:
    p = row[comp]
    if comp == "getiri":
        return f"Son 1 yılda {_p(row['ret_1y'])} getiri sağladı; {_vs_rf(row)} (risksiz getiri {_p(rf)}). Bu, {_bucket(p)}."
    if comp == "riske_gore":
        if row["low_vol"]:
            return f"Fiyatı neredeyse hiç dalgalanmıyor (volatilite {_p(row['vol'])}); {_vs_rf(row)} getiri sağladı ({_bucket(p)})."
        return f"Sharpe oranı {_num(row['sharpe'], 2)}: aldığı riske göre getirisi {_bucket(p)}."
    if comp == "dusus":
        if (row["mdd"] or 0) > -0.0005:
            return "Son 1 yılda kayda değer bir değer kaybı dönemi yaşamadı."
        return f"Son 1 yıldaki en büyük düşüşü -{_p(row['mdd'])} ile sınırlı kaldı ({_bucket(p)})."
    # tutarlilik
    if row["worst_ann"] - rf > 0:
        return "Son 3, 6 ve 12 aylık getirilerinin hepsi, yıllık bazda risksiz getirinin üstünde."
    return f"Getirisi dönemden döneme istikrarlı; en zayıf dönemi bile {_bucket(p)}."


def _caution(row, comp: str) -> str:
    if comp == "getiri":
        return "Dikkat: 1 yıllık getirisi adayların alt %25'inde."
    if comp == "riske_gore":
        return "Dikkat: aldığı riske göre getirisi adayların alt %25'inde."
    if comp == "dusus":
        return f"Dikkat: en büyük düşüşü -{_p(row['mdd'])} ile adayların en kötü %25'inde."
    return f"Dikkat: son {row['worst_period']} getirisi zayıf (yıllık bazda {'-' if row['worst_ann'] < 0 else ''}{_p(row['worst_ann'])})."


def explain(row, profile: str, rf: float) -> tuple[list[str], str | None]:
    """En güçlü iki bileşen + profil uyumu; en zayıf bileşen alt %25'teyse uyarı."""
    comps = sorted(COMPONENTS, key=lambda c: row[c], reverse=True)
    reasons = [_strength(row, c, rf) for c in comps[:2]]
    lo, hi = PROFILE_RULES[profile].risk_range
    reasons.append(f"TEFAS risk değeri {int(row['risk_level'])}, {PROFILE_LABELS[profile].lower()} profilin aralığında ({lo}-{hi}).")
    weakest = comps[-1]
    caution = _caution(row, weakest) if row[weakest] <= 0.25 else None
    return reasons, caution


# --- Portföy performansı -------------------------------------------------------

def load_prices(db: Session, codes: list[str] | None, since: date) -> pd.DataFrame:
    """Geniş tablo: satır tarih, sütun fon kodu."""
    stmt = select(Price.date, Price.fund_code, Price.price).where(Price.date >= since)
    if codes is not None:
        stmt = stmt.where(Price.fund_code.in_(codes))
    rows = db.execute(stmt).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "code", "price"])
    df["date"] = pd.to_datetime(df["date"])
    return df.pivot_table(index="date", columns="code", values="price", aggfunc="last").sort_index()


def normalized(wide: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Her fonu `start` günündeki (ya da öncesindeki son) fiyatında 100 yapar; dönem içinde verisi
    kesilen fon son fiyatında kalır (yatırımcı o fiyattan çıkamamış sayılır). Başlangıçta fiyatı
    olmayan fon (TOLERANS içinde) dışarıda kalır."""
    if wide.empty:
        return wide
    w = wide.loc[:end].ffill()
    base_rows = w.loc[:start]
    if base_rows.empty:
        return pd.DataFrame()
    base = base_rows.iloc[-1]
    last_seen = wide.loc[:start].apply(lambda s: s.last_valid_index())
    fresh = last_seen.notna() & (last_seen >= start - pd.Timedelta(days=STALE_AFTER_DAYS))
    base = base[fresh & base.notna()]
    out = w.loc[start:, base.index] / base * 100
    if out.empty or out.index[0] != start:
        out = pd.concat([pd.DataFrame([[100.0] * len(base)], index=[start], columns=base.index), out])
        out = out[~out.index.duplicated(keep="last")]
    return out


@dataclass
class Performance:
    start: date
    end: date
    series: pd.DataFrame  # sütunlar: portfolio, benchmark
    portfolio: dict
    benchmark: dict
    funds: dict[str, float] = field(default_factory=dict)  # fon -> dönem getirisi
    benchmark_funds: int = 0


def _stats(v: pd.Series) -> dict:
    r = v.pct_change().dropna()
    return {
        "return": float(v.iloc[-1] / v.iloc[0] - 1),
        "volatility": float(r.std() * math.sqrt(252)) if len(r) > 1 else None,
        "max_drawdown": float((v / v.cummax() - 1).min()),
    }


def performance(db: Session, codes: list[str], start: date, end: date, mm_codes: list[str]) -> Performance | None:
    """Eşit ağırlıklı, başlangıçta alınıp tutulan (yeniden dengelenmeyen) portföy ve para piyasası
    fonlarının medyanı (her gün, 100'den başlayan serilerin medyanı)."""
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    wide = load_prices(db, list(set(codes) | set(mm_codes)), start - timedelta(days=STALE_AFTER_DAYS + 7))
    if wide.empty:
        return None
    norm = normalized(wide, start_ts, end_ts)
    held = [c for c in codes if c in norm.columns]
    mm = [c for c in mm_codes if c in norm.columns]
    if not held or not mm:
        return None
    port = norm[held].mean(axis=1)  # eşit ağırlık, al-tut: başlangıç değerlerinin ortalaması
    bench = norm[mm].median(axis=1)
    series = pd.DataFrame({"portfolio": port, "benchmark": bench}).dropna()
    return Performance(
        start=start, end=series.index[-1].date(), series=series,
        portfolio=_stats(series["portfolio"]), benchmark=_stats(series["benchmark"]),
        funds={c: float(norm[c].dropna().iloc[-1] / 100 - 1) for c in held}, benchmark_funds=len(mm),
    )


# --- Öneri ----------------------------------------------------------------------

@dataclass
class Recommendation:
    profile: str
    qualified: bool
    as_of: date | None
    risk_free_rate: float | None
    pool_size: int
    items: pd.DataFrame  # seçilen fonlar (diversify sonrası), bileşenler ve puan
    reasons: dict[str, tuple[list[str], str | None]]
    portfolio: pd.DataFrame


def recommend_from(df: pd.DataFrame, as_of, profile: str, qualified: bool, limit: int = 10,
                   rf: float | None = None, ra_mode: str | None = None) -> Recommendation:
    rf = risk_free_from(df) if rf is None else rf
    pool = eligible(df, profile, qualified)
    if rf is None or pool.empty:
        empty = pool.iloc[0:0]
        return Recommendation(profile, qualified, as_of, rf, len(pool), empty, {}, empty)
    scored = score(pool, profile, rf, ra_mode=ra_mode)
    quota = RISKY_QUOTA.get(profile, 0)
    items = diversify(scored, limit, min_risky=quota)
    # kota olmasaydı listeye giremeyecek fonlar
    unconstrained = set(diversify(scored, limit)["code"]) if quota else set(items["code"])
    items = items.assign(quota=~items["code"].isin(unconstrained))
    reasons = {}
    for _, row in items.iterrows():
        why, caution = explain(row, profile, rf)
        if row["quota"]:
            why.append(f"{PROFILE_LABELS[profile]} profilde çeşitlendirme için önerilerin en az {quota}'si risk değeri "
                       f"{RISKY_MIN_LEVEL} ve üstü, gerçekten dalgalanan fonlardan seçilir; bu fon o gruptaki en yüksek puanlılardan.")
        reasons[row["code"]] = (why, caution)
    return Recommendation(profile, qualified, as_of, rf, len(pool), items, reasons,
                          portfolio_pick(items, PORTFOLIO_SIZE[profile], min_risky=quota))


def recommend(db: Session, profile: str, qualified: bool, limit: int = 10) -> Recommendation:
    df, latest = current_candidates(db)
    return recommend_from(df, latest, profile, qualified, limit)


def money_market_codes(db: Session) -> list[str]:
    # Kıyas için TÜM para piyasası fonları (sonradan kapatılanlar dahil): o dönemde yatırım
    # yapılabilen fonların medyanı, sadece bugün ayakta kalanlarınki değil.
    return list(db.scalars(select(Fund.code).where(Fund.category == RISK_FREE_CATEGORY)))


# --- Geriye dönük test ------------------------------------------------------------

ROLLING_YEARS = 3  # kayan pencere: son 3 yılda her ayın ilk işlem günü seçim
PROFILES_ALL = (TEMKINLI, DENGELI, AGRESIF)


@dataclass
class PriceHistory:
    """Bir kez yüklenip her pencerede kullanılan fiyat geçmişi."""
    series: dict[str, pd.Series]  # fon -> tek günlük hataları çıkarılmış fiyat serisi
    wide: pd.DataFrame  # satır tarih, sütun fon (performans hesabı için)
    meta: dict[str, tuple]  # fon -> (ad, kategori, risk değeri)


def load_history(db: Session, since: date) -> PriceHistory:
    rows = db.execute(select(Price.fund_code, Price.date, Price.price).where(Price.date >= since)).all()
    meta = {c: (n, cat, rl) for c, n, cat, rl in db.execute(select(Fund.code, Fund.name, Fund.category, Fund.risk_level))}
    prices = pd.DataFrame(rows, columns=["code", "date", "price"])
    if prices.empty:
        return PriceHistory({}, pd.DataFrame(), meta)
    prices["date"] = pd.to_datetime(prices["date"])
    series = {c: drop_one_day_glitches(g.sort_values("date").set_index("date")["price"]) for c, g in prices.groupby("code")}
    wide = prices.pivot_table(index="date", columns="code", values="price", aggfunc="last").sort_index()
    return PriceHistory(series, wide, meta)


def frame_as_of(hist: PriceHistory, when: date) -> pd.DataFrame:
    """`when` tarihine kadarki fiyatlarla hesaplanan metriklerle aday havuzu.

    O tarihte fiyatı olan (STALE_AFTER_DAYS içinde) tüm fonlar adaydır; sonradan kapatılan ya da
    verisi kesilen fonlar da dahil (geleceği bilmeden seçim). Risk değeri ve kategori için
    elimizde sadece bugünkü değerler var.
    """
    when_ts = pd.Timestamp(when)
    cutoff = when_ts - pd.Timedelta(days=STALE_AFTER_DAYS)
    since = when_ts - pd.Timedelta(days=400)
    out = []
    for code, full in hist.series.items():
        s = full.loc[since:when_ts]
        if s.empty or s.index[-1] < cutoff:
            continue
        m = compute_fund_metrics(s)
        if m is None or m.ret_1y is None or m.volatility_1y is None:
            continue
        name, cat, rl = hist.meta.get(code, (code, None, None))
        out.append((code, name, cat, rl, m.ret_3m, m.ret_6m, m.ret_1y, m.volatility_1y, None, m.max_drawdown_1y, m.as_of))
    df = pd.DataFrame(out, columns=FRAME_COLUMNS)
    rf = risk_free_from(df)
    if rf is not None and not df.empty:
        ok = df["vol"] >= MIN_VOL_FOR_SHARPE
        df.loc[ok, "sharpe"] = (df.loc[ok, "ret_1y"] - rf) / df.loc[ok, "vol"]
    return df


_frame_cache: dict = {}


def candidates_as_of(db: Session, when: date) -> pd.DataFrame:
    key = (id(db.get_bind()), when, db.scalar(select(func.count()).select_from(Price)))
    if key not in _frame_cache:
        _frame_cache.clear()  # sadece en son tarih saklanır
        _frame_cache[key] = frame_as_of(load_history(db, when - timedelta(days=400)), when)
    return _frame_cache[key]


@dataclass
class Backtest:
    selection_date: date
    recommendation: Recommendation
    performance: Performance | None


def backtest(db: Session, profile: str, qualified: bool, months: int = BACKTEST_MONTHS) -> Backtest | None:
    """Tek dönem: 12 ay önceki veriyle seçim, sonraki 12 ayın performansı (analiz betiği için)."""
    latest = db.scalar(select(func.max(Price.date)))
    if latest is None:
        return None
    when = (pd.Timestamp(latest) - pd.DateOffset(months=months)).date()
    df = candidates_as_of(db, when)
    rec = recommend_from(df, when, profile, qualified)
    perf = None
    if not rec.portfolio.empty:
        perf = performance(db, list(rec.portfolio["code"]), when, latest, money_market_codes(db))
    return Backtest(when, rec, perf)


def selection_dates(db: Session, years: int = ROLLING_YEARS, horizon_months: int = BACKTEST_MONTHS) -> list[date]:
    """Son `years` yıl içinde, ardından `horizon_months` aylık veri olan her ayın ilk işlem günü."""
    latest = db.scalar(select(func.max(Price.date)))
    if latest is None:
        return []
    first = (pd.Timestamp(latest) - pd.DateOffset(years=years)).date()
    last = (pd.Timestamp(latest) - pd.DateOffset(months=horizon_months)).date()
    days = sorted(set(db.scalars(select(Price.date).where(Price.date >= first, Price.date <= last).distinct())))
    by_month: dict[tuple[int, int], date] = {}
    for d in days:
        by_month.setdefault((d.year, d.month), d)
    # dönemin ilk ayı ayın ortasından başlıyorsa o ay atlanır (seçim "ayın başında")
    return [d for d in by_month.values() if d.day <= 7]


@dataclass
class Window:
    profile: str
    qualified: bool
    start: date
    end: date
    codes: list[str]
    portfolio_return: float
    benchmark_return: float

    @property
    def excess(self) -> float:
        return self.portfolio_return - self.benchmark_return


def window_returns(hist: PriceHistory, codes: list[str], mm_codes: list[str], start: date, end: date) -> tuple[float, float] | None:
    """Eşit ağırlıklı al-tut portföy ve para piyasası medyanının dönem getirisi."""
    norm = normalized(hist.wide, pd.Timestamp(start), pd.Timestamp(end))
    if norm.empty:
        return None
    held = [c for c in codes if c in norm.columns]
    mm = [c for c in mm_codes if c in norm.columns]
    if not held or not mm:
        return None
    return float(norm[held].mean(axis=1).iloc[-1] / 100 - 1), float(norm[mm].median(axis=1).iloc[-1] / 100 - 1)


def rolling_backtest(db: Session, years: int = ROLLING_YEARS, horizon_months: int = BACKTEST_MONTHS,
                     profiles=PROFILES_ALL, qualified_options=(False, True)) -> list[Window]:
    dates = selection_dates(db, years, horizon_months)
    if not dates:
        return []
    hist = load_history(db, dates[0] - timedelta(days=400))
    mm_codes = money_market_codes(db)
    windows = []
    for start in dates:
        end = (pd.Timestamp(start) + pd.DateOffset(months=horizon_months)).date()
        frame = frame_as_of(hist, start)
        for profile in profiles:
            for qualified in qualified_options:
                rec = recommend_from(frame, start, profile, qualified)
                if rec.portfolio.empty:
                    continue
                codes = list(rec.portfolio["code"])
                r = window_returns(hist, codes, mm_codes, start, end)
                if r:
                    windows.append(Window(profile, qualified, start, end, codes, r[0], r[1]))
    return windows


def summarize_windows(windows: list[Window]) -> dict | None:
    if not windows:
        return None
    ex = pd.Series([w.excess for w in windows])
    return {
        "windows": len(windows),
        "beats": int((ex > 0).sum()),
        "mean_excess": float(ex.mean()),
        "median_excess": float(ex.median()),
        "mean_portfolio": float(pd.Series([w.portfolio_return for w in windows]).mean()),
        "mean_benchmark": float(pd.Series([w.benchmark_return for w in windows]).mean()),
        "best": max(windows, key=lambda w: w.excess),
        "worst": min(windows, key=lambda w: w.excess),
    }


def store_rolling(db: Session) -> int:
    """Kayan pencereli testi hesaplayıp backtest_windows tablosuna yazar (öncekileri siler)."""
    windows = rolling_backtest(db)
    as_of = db.scalar(select(func.max(Price.date)))
    db.execute(delete(BacktestWindow))
    db.add_all(BacktestWindow(profile=w.profile, qualified=w.qualified, start_date=w.start, end_date=w.end,
                              codes=",".join(w.codes), portfolio_return=w.portfolio_return,
                              benchmark_return=w.benchmark_return, data_as_of=as_of) for w in windows)
    db.commit()
    return len(windows)


def load_windows(db: Session, profile: str, qualified: bool) -> list[Window]:
    rows = db.scalars(select(BacktestWindow)
                      .where(BacktestWindow.profile == profile, BacktestWindow.qualified.is_(qualified))
                      .order_by(BacktestWindow.start_date))
    return [Window(r.profile, r.qualified, r.start_date, r.end_date, r.codes.split(","), r.portfolio_return,
                   r.benchmark_return) for r in rows]
