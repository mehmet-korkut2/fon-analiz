"""Benzer fonlar, kümeleme ve çeşitlendirme (rapor 6.11).

Benzerlik ölçüsü son 1 yılın HAFTALIK getiri korelasyonudur. Günlük getiri kullanılmaz: para piyasası benzeri
fonlarda hafta sonu faizi pazartesi fiyatına yansıdığı için (pazartesi getirisi diğer günlerin ~3 katı) günlük
getiriler takvim yüzünden birbirine benzer görünür; bayram tatilleri de benzer bir etki yapar. Haftalık getiri
bu etkileri haftanın içinde eritir. 53 haftalık gözlemin gürültüsünü azaltmak için hafta pazartesiden cumaya
her gün başlatılır (5 çapa) ve 5 korelasyon matrisinin ortalaması alınır.

Uzaklık d = sqrt(2(1 - rho)) (Mantegna 1999): standartlaştırılmış getiri vektörleri arasındaki Öklid uzaklığı
olduğu için Ward bağlantısıyla kullanılabilir. Küme sayısı K_RANGE içinde ortalama silhouette en yüksek olan k.
Doğrulama: TEFAS kategorileriyle düzeltilmiş Rand indeksi (ARI) ve bir önceki yılın kümeleriyle ARI (kararlılık).

Kümeler ve en yakın 5 fon ayda bir (REFRESH_DAYS) hesaplanıp similarity_runs / fund_clusters / fund_neighbors
tablolarına yazılır. Seçilen birkaç fonun korelasyonu (karşılaştırma, portföy uyarıları) anlık hesaplanır.
Öneri puanlaması bu sonuçları kullanmaz.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import spearmanr
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Fund, FundCluster, FundMetrics, FundNeighbor, Price, SimilarityRun
from app.services.data_quality import drop_one_day_glitches
from app.services.fund_status import is_tradable
from app.services.metrics import MIN_VOL_FOR_SHARPE

log = logging.getLogger(__name__)

METHOD_VERSION = "haftalik5-ward-v1"
WINDOW_DAYS = 365
ANCHORS = ("W-MON", "W-TUE", "W-WED", "W-THU", "W-FRI")
MIN_OVERLAP = 0.8  # iki fonun ortak getirisi olan hafta oranı en az bu kadar olmalı
MIN_PRICES = 200  # 1 yıllık pencerede en az bu kadar fiyat (yaklaşık 250 işlem günü)
EDGE_DAYS = 7  # pencerenin başında ve sonunda fiyat bu kadar gün içinde olmalı
HIGH_CORR = 0.90  # çeşitlendirme uyarısı eşiği
N_NEIGHBORS = 5
K_RANGE = range(5, 21)  # k=2-4 yalnızca "riskli / risksiz" gibi kaba ayrımlar verir
REFRESH_DAYS = 28
DIFFUSE_CORR = 0.30  # kümenin iç medyan korelasyonu bunun altındaysa belirgin bir grup sayılmaz
HOMOGENEOUS = ("Hisse Senedi", "Para Piyasası", "Borçlanma Araçları", "Kıymetli Madenler")
DIFFUSE_NAME = "Belirgin bir gruba girmeyen fonlar"
LOW_VOL = MIN_VOL_FOR_SHARPE  # iki fonun da oynaklığı bunun altındaysa uyarı metni yumuşar


# --- veri -----------------------------------------------------------------------------------------

def load_wide(db: Session, start: date, end: date, codes: list[str] | None = None) -> pd.DataFrame:
    """[start - 10 gün, end] aralığındaki fiyatlar; sütun = fon, satır = tarih. Tek günlük hatalı fiyatlar çıkarılır."""
    q = select(Price.fund_code, Price.date, Price.price).where(
        Price.date > start - timedelta(days=10), Price.date <= end, Price.price > 0)
    if codes is not None:
        q = q.where(Price.fund_code.in_(codes))
    rows = db.execute(q).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["code", "date", "price"])
    df["date"] = pd.to_datetime(df["date"])
    series = {c: drop_one_day_glitches(g.set_index("date")["price"].sort_index()) for c, g in df.groupby("code")}
    return pd.DataFrame(series).sort_index()


def window(wide: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    return wide.loc[(wide.index > s - pd.Timedelta(days=10)) & (wide.index <= e)]


def coverage_ok(wide: pd.DataFrame, start: date, end: date) -> pd.Series:
    """Fonun [start, end] penceresini kapsayan yeterli fiyatı var mı (fon başına True/False)."""
    w = window(wide, start, end)
    if w.empty:
        return pd.Series(dtype=bool)
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    first = w.apply(lambda c: c.first_valid_index())
    last = w.apply(lambda c: c.last_valid_index())
    n = w.loc[w.index > s].notna().sum()
    return (first.notna() & (first <= s + pd.Timedelta(days=EDGE_DAYS)) & last.notna()
            & (last >= e - pd.Timedelta(days=EDGE_DAYS)) & (n >= MIN_PRICES))


def missing_reason(wide: pd.DataFrame, code: str, start: date, end: date) -> str:
    if code not in wide.columns or wide[code].notna().sum() == 0:
        return "fiyat verisi yok"
    s = wide[code].dropna()
    if s.index[-1] < pd.Timestamp(end) - pd.Timedelta(days=EDGE_DAYS):
        return "son fiyatı eski"
    return "1 yıllık fiyat verisi yok"


def weekly_returns(wide: pd.DataFrame, anchor: str, start: date) -> pd.DataFrame:
    """Haftanın `anchor` gününde biten haftalık getiriler (o güne kadarki son fiyat)."""
    p = wide.ffill(limit=5).resample(anchor).last()
    r = p.pct_change(fill_method=None)
    return r.loc[r.index > pd.Timestamp(start)]


def weekly_corr(wide: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """5 çapalı haftalık getiri korelasyonu. Ortak haftası az olan çift NaN."""
    w = window(wide, start, end)
    mats = []
    for a in ANCHORS:
        r = weekly_returns(w, a, start)
        mats.append(r.corr(min_periods=max(3, int(np.ceil(MIN_OVERLAP * len(r))))))
    return sum(mats) / len(mats)


def daily_corr(wide: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Karşılaştırma için: ham günlük getiri korelasyonu (pazartesi etkisini gösterir)."""
    r = window(wide, start, end).ffill(limit=3).pct_change(fill_method=None)
    r = r.loc[r.index > pd.Timestamp(start)]
    return r.corr(min_periods=int(MIN_OVERLAP * len(r)))


# --- ölçüler --------------------------------------------------------------------------------------

def corr_distance(C) -> np.ndarray:
    C = np.asarray(C, dtype=float)
    D = np.sqrt(np.clip(2 * (1 - C), 0, None))
    np.fill_diagonal(D, 0)
    return D


def silhouette_samples(D: np.ndarray, labels) -> np.ndarray:
    """Önceden hesaplanmış uzaklık matrisiyle fon başına silhouette (Rousseeuw 1987). Tek elemanlı küme: 0."""
    lab = np.asarray(labels)
    u = np.unique(lab)
    if len(u) < 2:
        return np.zeros(len(lab))
    li = np.searchsorted(u, lab)
    M = np.zeros((len(lab), len(u)))
    M[np.arange(len(lab)), li] = 1
    cnt = M.sum(0)
    S = D @ M
    own = cnt[li]
    a = S[np.arange(len(lab)), li] / np.maximum(own - 1, 1)
    other = S / cnt
    other[np.arange(len(lab)), li] = np.inf
    b = other.min(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        s = (b - a) / np.maximum(a, b)
    return np.where((own > 1) & np.isfinite(s), s, 0.0)


def silhouette(D: np.ndarray, labels) -> float:
    return float(silhouette_samples(D, labels).mean())


def adjusted_rand(a, b) -> float:
    """Düzeltilmiş Rand indeksi (Hubert ve Arabie 1985): 1 aynı bölümleme, ~0 rastgele."""
    a, b = np.asarray(a), np.asarray(b)
    if len(a) < 2:
        return float("nan")
    ct = pd.crosstab(a, b).to_numpy().astype(float)
    c2 = lambda x: x * (x - 1) / 2  # noqa: E731
    sij = c2(ct).sum()
    sa, sb = c2(ct.sum(1)).sum(), c2(ct.sum(0)).sum()
    expected = sa * sb / c2(len(a))
    maximum = (sa + sb) / 2
    if maximum == expected:
        return 1.0
    return float((sij - expected) / (maximum - expected))


def ward_tree(D: np.ndarray):
    return linkage(squareform(D, checks=False), method="ward")


def cut(Z, k: int) -> np.ndarray:
    return fcluster(Z, k, criterion="maxclust")


def choose_k(D: np.ndarray, Z, ks=K_RANGE) -> tuple[int, list[dict]]:
    curve = [{"k": k, "silhouette": silhouette(D, cut(Z, k))} for k in ks if k < len(D)]
    if not curve:
        return 1, []
    best = max(curve, key=lambda r: (round(r["silhouette"], 6), -r["k"]))
    return best["k"], curve


def nearest(C: pd.DataFrame, code: str, n: int = N_NEIGHBORS) -> list[tuple[str, float]]:
    s = C[code].drop(code).dropna().sort_values(ascending=False, kind="mergesort").head(n)
    return [(c, float(v)) for c, v in s.items()]


def effective_n(C, weights=None) -> float | None:
    """Etkin bağımsız fon sayısı 1 / (w' R w): eşit ağırlıklı ve tamamen bağımsız N fon için N, birbirinin aynısı
    fonlar için 1. Negatif korelasyonda fon sayısını aşabileceği için [1, N] aralığına kırpılır."""
    R = np.asarray(C, dtype=float)
    n = len(R)
    if n == 0 or np.isnan(R).any():
        return None
    w = np.full(n, 1 / n) if weights is None else np.asarray(weights, dtype=float)
    if w.sum() <= 0:
        return None
    w = w / w.sum()
    v = float(w @ R @ w)
    return float(n) if v <= 0 else float(min(max(1 / v, 1.0), n))


def mean_corr(C, weights=None) -> float | None:
    R = np.asarray(C, dtype=float)
    n = len(R)
    if n < 2 or np.isnan(R).any():
        return None
    w = np.full(n, 1 / n) if weights is None else np.asarray(weights, dtype=float)
    W = np.outer(w, w)
    np.fill_diagonal(W, 0)
    return float((W * R).sum() / W.sum()) if W.sum() > 0 else None


def high_pairs(C: pd.DataFrame, threshold: float = HIGH_CORR) -> list[tuple[str, str, float]]:
    codes = list(C.index)
    out = []
    for i, a in enumerate(codes):
        for b in codes[i + 1:]:
            v = C.loc[a, b]
            if pd.notna(v) and v >= threshold:
                out.append((a, b, float(v)))
    return sorted(out, key=lambda t: -t[2])


# --- küme adları ----------------------------------------------------------------------------------

def _share(names: list[str], pattern: str) -> float:
    rx = re.compile(pattern)
    return sum(bool(rx.search(n)) for n in names) / max(len(names), 1)


def name_cluster(names: list[str], categories: list[str], median_vol: float | None, internal_corr: float) -> str:
    """Kümeye içeriğinden ad verir (küme numaraları her hesapta değişebilir). Kurallar fon adlarındaki anahtar
    kelimelere, kategoriye ve oynaklığa bakar; hiçbiri tutmazsa baskın kategori."""
    if internal_corr < DIFFUSE_CORR:
        return DIFFUSE_NAME
    names = [n.upper() for n in names]
    vol = median_vol if median_vol is not None else 1.0
    cats = pd.Series(categories).value_counts(normalize=True)
    if _share(names, r"ALTIN|GÜMÜŞ|KIYMETLİ MADEN|METAL") >= 0.5:
        return "Altın ve kıymetli madenler"
    if _share(names, r"AVRO|EURO(?!BOND)|\bEUR\b") >= 0.5:
        return "Avro bazlı fonlar"
    if _share(names, r"DÖVİZ|DOLAR|USD|EUROBOND|YABANCI BORÇ") >= 0.4:
        return "Dolar bazlı fonlar" if vol < 0.02 else "Döviz ve eurobond ağırlıklı fonlar"
    if _share(names, r"PARA PİYASASI|KISA VADELİ|LİKİT") >= 0.3 and vol < 0.04:
        return "TL para piyasası benzeri fonlar"
    if _share(names, r"BORÇLANMA|TAHVİL|BONO|KİRA SERTİFİKA") >= 0.5:
        return "TL tahvil ve bono fonları"
    if _share(names, r"YABANCI|TEKNOLOJİ|GLOBAL|AMERİKA|ABD") >= 0.4:
        return "Yabancı ve teknoloji hisseleri"
    if cats.get("Hisse Senedi", 0) >= 0.4 or _share(names, r"HİSSE") >= 0.5:
        return "Yerli hisse ağırlıklı fonlar"
    if cats.get("Fon Sepeti", 0) + cats.get("Değişken", 0) + cats.get("Karma", 0) >= 0.5:
        return "Fon sepeti, değişken ve karma fonlar"
    if vol < 0.04:
        return "Düşük oynaklıklı TL fonlar"
    return f"{cats.index[0]} ağırlıklı fonlar" if len(cats) else "Diğer fonlar"


def _unique(names: list[str]) -> list[str]:
    """Aynı adı alan kümelere sıra numarası ekler (belirgin grubu olmayanlar hariç)."""
    seen: dict[str, int] = {}
    out = []
    for n in names:
        if n == DIFFUSE_NAME:
            out.append(n)
            continue
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n} ({seen[n]})")
    return out


# --- ayda bir hesap -------------------------------------------------------------------------------

def _upper(C: np.ndarray) -> np.ndarray:
    v = C[np.triu_indices(len(C), 1)]
    return v[~np.isnan(v)]


def compute(db: Session, end: date | None = None) -> dict | None:
    """Kümeleme ve en yakın fonlar. Kaydetmez; payload, fon kümeleri ve komşuları döndürür."""
    end = end or db.scalar(select(func.max(Price.date)))
    if end is None:
        return None
    start = end - timedelta(days=WINDOW_DAYS)
    prev_start = start - timedelta(days=WINDOW_DAYS)
    tradable = set(db.scalars(select(Fund.code).where(is_tradable())))
    wide = load_wide(db, prev_start, end)
    if wide.empty:
        return None
    ok = coverage_ok(wide, start, end)
    codes = sorted(c for c in ok.index[ok] if c in tradable)
    if len(codes) < max(K_RANGE.start, 3) * 2:
        return None
    Cdf = weekly_corr(wide[codes], start, end)
    C = Cdf.to_numpy(copy=True)
    C = np.where(np.isnan(C), 0.0, C)  # sabit fiyatlı fon gibi tanımsız korelasyon: ilişkisiz say
    np.fill_diagonal(C, 1.0)
    D = corr_distance(C)
    Z = ward_tree(D)
    k, curve = choose_k(D, Z)
    labels = cut(Z, k)
    sil = silhouette_samples(D, labels)

    info = pd.DataFrame(db.execute(select(Fund.code, Fund.name, Fund.category).where(Fund.code.in_(codes))).all(),
                        columns=["code", "name", "category"]).set_index("code").reindex(codes)
    met = pd.DataFrame(db.execute(select(FundMetrics.fund_code, FundMetrics.volatility_1y, FundMetrics.ret_1y)
                                  .where(FundMetrics.fund_code.in_(codes))).all(),
                       columns=["code", "vol", "ret"]).set_index("code").reindex(codes).astype(float)
    cat = info["category"].fillna("Diğer").to_numpy()

    # kümeleri büyükten küçüğe numarala
    order = pd.Series(labels).value_counts().index.tolist()
    relabel = {old: i + 1 for i, old in enumerate(order)}
    labels = np.array([relabel[x] for x in labels])

    clusters = []
    for cid in range(1, k + 1):
        m = labels == cid
        idx = np.where(m)[0]
        inner = _upper(C[np.ix_(m, m)])
        internal = float(np.median(inner)) if len(inner) else 1.0
        medoid = codes[idx[D[np.ix_(m, m)].sum(1).argmin()]]
        vols = met["vol"].to_numpy()[m]
        median_vol = float(np.nanmedian(vols)) if np.isfinite(vols).any() else None
        rets = met["ret"].to_numpy()[m]
        cats_top = pd.Series(cat[m]).value_counts().head(4)
        clusters.append({
            "id": cid, "size": int(m.sum()), "internal_corr": internal, "silhouette": float(sil[m].mean()),
            "median_vol": median_vol, "median_ret_1y": float(np.nanmedian(rets)) if np.isfinite(rets).any() else None,
            "representative": medoid, "diffuse": internal < DIFFUSE_CORR,
            "categories": [{"category": c, "n": int(n)} for c, n in cats_top.items()],
            "name": name_cluster(info["name"].fillna("").to_numpy()[m].tolist(), cat[m].tolist(), median_vol, internal),
        })
    for c, n in zip(clusters, _unique([c["name"] for c in clusters])):
        c["name"] = n

    homo = np.isin(cat, HOMOGENEOUS)
    payload = {
        "method_version": METHOD_VERSION, "data_as_of": end.isoformat(), "window_start": start.isoformat(),
        "n_funds": len(codes), "k": k, "silhouette": float(sil.mean()), "silhouette_curve": curve,
        "ari_category": adjusted_rand(labels, cat),
        "ari_homogeneous": adjusted_rand(labels[homo], cat[homo]) if homo.sum() > 1 else None,
        "homogeneous_categories": list(HOMOGENEOUS), "threshold": HIGH_CORR,
        "clusters": clusters,
    }
    vals = _upper(Cdf.to_numpy())
    payload["pairs"] = {"n": int(len(vals)), "median": float(np.median(vals)) if len(vals) else None,
                        "share_high": float((vals >= HIGH_CORR).mean()) if len(vals) else None,
                        "n_high": int((vals >= HIGH_CORR).sum())}

    # pazartesi etkisi: para piyasası fonları arası medyan korelasyon, günlük ve haftalık
    mm = [i for i, c in enumerate(cat) if c == "Para Piyasası"]
    if len(mm) >= 3:
        Cd = daily_corr(wide[codes], start, end).to_numpy()
        sub = np.ix_(mm, mm)
        payload["monday_effect"] = {"n": len(mm), "daily": float(np.median(_upper(Cd[sub]))),
                                    "weekly": float(np.median(_upper(Cdf.to_numpy()[sub])))}

    # kararlılık ve kalıcılık: bir önceki yıl
    okp = coverage_ok(wide, prev_start, start)
    both = [c for c in codes if c in okp.index and okp[c]]
    if len(both) >= max(K_RANGE.start, 3) * 2:
        Cp = weekly_corr(wide[both], prev_start, start).to_numpy(copy=True)
        Cp = np.where(np.isnan(Cp), 0.0, Cp)
        np.fill_diagonal(Cp, 1.0)
        Zp = ward_tree(corr_distance(Cp))
        pos = [codes.index(c) for c in both]
        Cb = C[np.ix_(pos, pos)]
        for row in curve:  # aynı k ile iki yılın kümeleri
            row["stability"] = adjusted_rand(cut(Z, row["k"])[pos], cut(Zp, row["k"]))
        stab = next(r["stability"] for r in curve if r["k"] == k)
        x, y = Cp[np.triu_indices(len(both), 1)], Cb[np.triu_indices(len(both), 1)]
        A0, A1 = Cp.copy(), Cb.copy()
        np.fill_diagonal(A0, -9)
        np.fill_diagonal(A1, -9)
        n0 = np.argsort(-A0, 1)[:, :N_NEIGHBORS]
        n1 = np.argsort(-A1, 1)[:, :N_NEIGHBORS]
        w = window(wide[both], prev_start, end).ffill()
        p_s, p_m, p_e = (w.loc[:pd.Timestamp(d)].iloc[-1] for d in (prev_start, start, end))
        r0, r1 = p_m / p_s - 1, p_e / p_m - 1
        high0 = x >= HIGH_CORR
        payload["stability"] = {
            "n_funds": len(both), "ari": stab,
            "neighbor_overlap": float(np.mean([len(set(a) & set(b)) / N_NEIGHBORS for a, b in zip(n0, n1)])),
            "prev_neighbors_corr_now": float(np.median(np.take_along_axis(Cb, n0, 1))),
            "best_neighbors_corr_now": float(np.median(np.take_along_axis(Cb, n1, 1))),
            "random_pair_corr_now": float(np.median(y)),
            "corr_persistence": float(spearmanr(x, y).statistic),
            "return_persistence": float(spearmanr(r0, r1, nan_policy="omit").statistic),
            "high_pairs_prev": int(high0.sum()),
            "high_pairs_still_08": float((y[high0] >= 0.8).mean()) if high0.any() else None,
        }
        eq = [i for i, c in enumerate(both) if cat[codes.index(c)] == "Hisse Senedi"]
        if len(eq) >= 15:
            payload["stability"]["return_persistence_equity"] = float(spearmanr(r0.iloc[eq], r1.iloc[eq], nan_policy="omit").statistic)

    cluster_rows = [{"fund_code": c, "cluster": int(labels[i]), "silhouette": float(sil[i])} for i, c in enumerate(codes)]
    neighbor_rows = []
    for c in codes:
        for rank, (o, v) in enumerate(nearest(Cdf, c), start=1):
            neighbor_rows.append({"fund_code": c, "rank": rank, "neighbor_code": o, "corr": v})
    return {"payload": payload, "clusters": cluster_rows, "neighbors": neighbor_rows}


def save(db: Session, result: dict) -> SimilarityRun:
    run = SimilarityRun(data_as_of=date.fromisoformat(result["payload"]["data_as_of"]), payload=result["payload"])
    db.add(run)
    db.flush()
    db.execute(delete(FundCluster).where(FundCluster.run_id != run.id))
    db.execute(delete(FundNeighbor).where(FundNeighbor.run_id != run.id))
    db.add_all(FundCluster(run_id=run.id, **r) for r in result["clusters"])
    db.add_all(FundNeighbor(run_id=run.id, **r) for r in result["neighbors"])
    db.commit()
    return run


def latest_run(db: Session) -> SimilarityRun | None:
    return db.scalars(select(SimilarityRun).order_by(SimilarityRun.created_at.desc(), SimilarityRun.id.desc()).limit(1)).first()


def run_if_due(db: Session, force: bool = False) -> dict:
    last = latest_run(db)
    age = (datetime.now() - last.created_at).days if last else None
    if not force and last is not None and age < REFRESH_DAYS and last.payload.get("method_version") == METHOD_VERSION:
        return {"skipped": f"son hesap {age} gün önce"}
    result = compute(db)
    if result is None:
        log.info("Benzerlik hesabı atlandı: yeterli veri yok")
        return {"skipped": "yeterli veri yok"}
    run = save(db, result)
    p = run.payload
    log.info("Benzerlik: %s fon, k=%s, silhouette %.3f", p["n_funds"], p["k"], p["silhouette"])
    return {"run_id": run.id, "n_funds": p["n_funds"], "k": p["k"]}


# --- API yardımcıları -----------------------------------------------------------------------------

def fund_similarity(db: Session, code: str) -> dict | None:
    run = latest_run(db)
    if run is None:
        return None
    row = db.get(FundCluster, (run.id, code))
    neighbors = db.scalars(select(FundNeighbor).where(FundNeighbor.run_id == run.id, FundNeighbor.fund_code == code)
                           .order_by(FundNeighbor.rank)).all()
    cluster = None
    if row is not None:
        cluster = next((c for c in run.payload["clusters"] if c["id"] == row.cluster), None)
    return {"run": run, "row": row, "cluster": cluster, "neighbors": neighbors}


def analyze(db: Session, codes: list[str], weights: list[float] | None = None, end: date | None = None) -> dict:
    """Seçilen fonların anlık korelasyonu, yüksek korelasyonlu çiftler ve çeşitlendirme skoru."""
    codes = list(dict.fromkeys(c.upper() for c in codes))
    end = end or db.scalar(select(func.max(Price.date)))
    out = {"as_of": end, "codes": codes, "ok": [], "missing": [], "matrix": [], "pairs": [], "n_eff": None,
           "mean_corr": None, "threshold": HIGH_CORR}
    if end is None or not codes:
        out["missing"] = [{"code": c, "reason": "fiyat verisi yok"} for c in codes]
        return out
    start = end - timedelta(days=WINDOW_DAYS)
    wide = load_wide(db, start, end, codes)
    good = coverage_ok(wide, start, end) if not wide.empty else pd.Series(dtype=bool)
    ok = [c for c in codes if c in good.index and good[c]]
    out["missing"] = [{"code": c, "reason": missing_reason(wide, c, start, end)} for c in codes if c not in ok]
    out["ok"] = ok
    if len(ok) < 2:
        return out
    C = weekly_corr(wide[ok], start, end).reindex(index=ok, columns=ok)
    for c in ok:
        C.loc[c, c] = 1.0
    out["matrix"] = [[None if pd.isna(v) else float(v) for v in row] for row in C.to_numpy()]
    vols = dict(db.execute(select(FundMetrics.fund_code, FundMetrics.volatility_1y).where(FundMetrics.fund_code.in_(ok))).all())
    out["pairs"] = [{"a": a, "b": b, "corr": v,
                     "low_vol": all(vols.get(x) is not None and vols[x] < LOW_VOL for x in (a, b))}
                    for a, b, v in high_pairs(C)]
    w = None
    if weights is not None:
        wmap = dict(zip(codes, weights))
        w = [max(float(wmap.get(c) or 0), 0.0) for c in ok]
        if sum(w) <= 0:
            w = None
    out["n_eff"] = effective_n(C.to_numpy(), w)
    out["mean_corr"] = mean_corr(C.to_numpy(), w)
    return out
