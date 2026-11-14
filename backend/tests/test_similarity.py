"""Benzer fonlar, kümeleme ve çeşitlendirme (app/ml/similarity.py): korelasyon ve uzaklık, silhouette ve ARI,
pazartesi etkisi (günlük / haftalık), k-NN, uyarı eşiği, etkin fon sayısı, eksik veri, kayıt ve API."""
from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.ml import similarity as S
from app.models import Fund, FundCluster, FundMetrics, FundNeighbor, Price, SimilarityRun
from app.services.fund_status import STATUS_CLOSED

END = date(2026, 11, 13)
IDX = pd.bdate_range("2024-11-01", END)


# --- saf hesaplar ---------------------------------------------------------------------------------

def test_corr_distance_values():
    C = np.array([[1, 1, 0, -1], [1, 1, 0, -1], [0, 0, 1, 0], [-1, -1, 0, 1]], dtype=float)
    D = S.corr_distance(C)
    assert D[0, 1] == 0 and D[0, 2] == pytest.approx(np.sqrt(2)) and D[0, 3] == pytest.approx(2)
    assert np.allclose(D, D.T) and np.all(np.diag(D) == 0)


def test_corr_distance_is_euclidean_between_standardized_returns():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(3, 50))
    Z = (X - X.mean(1, keepdims=True)) / X.std(1, keepdims=True) / np.sqrt(50)
    D = S.corr_distance(np.corrcoef(X))
    assert D[0, 1] == pytest.approx(np.linalg.norm(Z[0] - Z[1]))


def test_silhouette_hand_computed():
    pos = np.array([0, 1, 10, 11], dtype=float)
    D = np.abs(pos[:, None] - pos[None, :])
    s = S.silhouette_samples(D, [1, 1, 2, 2])
    assert s[0] == pytest.approx((10.5 - 1) / 10.5)  # a=1, b=(10+11)/2
    assert s[1] == pytest.approx((9.5 - 1) / 9.5)
    assert S.silhouette(D, [1, 1, 2, 2]) == pytest.approx(s.mean())
    assert S.silhouette_samples(D, [1, 1, 1, 2])[3] == 0  # tek elemanlı küme
    assert np.all(S.silhouette_samples(D, [1, 1, 1, 1]) == 0)


def test_adjusted_rand():
    assert S.adjusted_rand([0, 0, 1, 1], [5, 5, 7, 7]) == pytest.approx(1)  # etiket adı önemsiz
    # el hesabı: sij=2, sa=6, sb=3, beklenen 6*3/15=1.2, en büyük 4.5 -> 0.8/3.3
    assert S.adjusted_rand([0, 0, 0, 1, 1, 1], [0, 0, 1, 1, 2, 2]) == pytest.approx(0.8 / 3.3)
    rng = np.random.default_rng(1)
    assert abs(S.adjusted_rand(rng.integers(0, 4, 2000), rng.integers(0, 4, 2000))) < 0.02  # rastgele ~0


def test_high_pairs_threshold_boundary():
    C = pd.DataFrame([[1, 0.8999, 0.90], [0.8999, 1, np.nan], [0.90, np.nan, 1]], index=list("ABC"), columns=list("ABC"))
    assert S.high_pairs(C) == [("A", "C", 0.90)]
    assert S.high_pairs(C, threshold=0.85) == [("A", "C", 0.90), ("A", "B", 0.8999)]


def test_effective_n():
    assert S.effective_n(np.ones((3, 3))) == pytest.approx(1)  # birbirinin aynısı üç fon
    assert S.effective_n(np.eye(4)) == pytest.approx(4)
    assert S.effective_n(np.eye(2), [1, 0]) == pytest.approx(1)  # bütün para tek fonda
    assert S.effective_n(np.eye(2), [3, 1]) == pytest.approx(1 / (0.75**2 + 0.25**2))
    assert S.effective_n(np.array([[1, -0.5], [-0.5, 1]])) == 2  # negatif korelasyon fon sayısını aşamaz
    assert S.effective_n(np.array([[1, np.nan], [np.nan, 1]])) is None
    rho = 0.5
    C = np.full((3, 3), rho) + np.eye(3) * (1 - rho)
    assert S.effective_n(C) == pytest.approx(3 / (1 + 2 * rho))
    assert S.mean_corr(C) == pytest.approx(rho)


def test_nearest_excludes_self_and_missing():
    C = pd.DataFrame([[1, .9, .5, np.nan], [.9, 1, .2, .1], [.5, .2, 1, .3], [np.nan, .1, .3, 1]],
                     index=list("ABCD"), columns=list("ABCD"))
    assert S.nearest(C, "A", 5) == [("B", .9), ("C", .5)]


def test_name_cluster_rules():
    assert S.name_cluster(["X ALTIN FONU", "Y GÜMÜŞ FON SEPETİ"], ["Kıymetli Madenler"] * 2, 0.25, 0.9).startswith("Altın")
    assert S.name_cluster(["A SERBEST (DÖVİZ-AVRO) FON"] * 3, ["Serbest"] * 3, 0.05, 0.95) == "Avro bazlı fonlar"
    assert S.name_cluster(["A EUROBOND (DOLAR) FONU"] * 3, ["Borçlanma Araçları"] * 3, 0.01, 0.95) == "Dolar bazlı fonlar"
    assert S.name_cluster(["A HİSSE SENEDİ FONU"] * 3, ["Hisse Senedi"] * 3, 0.2, 0.2) == S.DIFFUSE_NAME
    assert S._unique(["A", "A", S.DIFFUSE_NAME, S.DIFFUSE_NAME]) == ["A", "A (2)", S.DIFFUSE_NAME, S.DIFFUSE_NAME]


# --- sentetik fiyatlar ----------------------------------------------------------------------------

def mm_prices(rng, weekly_rate_noise, common=None):
    """Para piyasası benzeri: her gün faiz, pazartesi 3 günlük (hafta sonu). Faiz haftadan haftaya değişir."""
    weeks = IDX.to_period("W")
    uw = weeks.unique()
    noise = pd.Series(rng.normal(0, weekly_rate_noise, len(uw)), index=uw)
    base = 0.0012 + (common if common is not None else 0) + noise.reindex(weeks).to_numpy()
    r = np.where(IDX.dayofweek == 0, 3 * base, base)
    return np.cumprod(1 + r)


def factor_prices(rng, factor, idio=0.3):
    r = factor + rng.normal(0, idio * factor.std(), len(factor))
    return np.cumprod(1 + r)


GROUPS = {"EQ": ("Hisse Senedi", "HİSSE SENEDİ FONU"), "AU": ("Kıymetli Madenler", "ALTIN FONU"),
          "US": ("Serbest", "SERBEST (DÖVİZ) FON"), "TB": ("Borçlanma Araçları", "UZUN VADELİ BORÇLANMA ARAÇLARI FONU"),
          "EN": ("Değişken", "ENERJİ DEĞİŞKEN FON")}


@pytest.fixture
def Session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sm = sessionmaker(bind=engine)
    rng = np.random.default_rng(42)
    prices = {}
    meta = {}
    for g, (cat, label) in GROUPS.items():
        f = rng.normal(0.0005, 0.012, len(IDX))
        for i in range(6):
            code = f"{g}{i}"
            prices[code] = factor_prices(rng, f)
            meta[code] = (cat, f"{g} PORTFÖY {i}. {label}")
    common = np.repeat(rng.normal(0, 0.0003, len(IDX) // 5 + 1), 5)[:len(IDX)]
    for i in range(4):  # kendi aralarında aynı faiz yolunu izleyen para piyasası fonları
        prices[f"MM{i}"] = mm_prices(rng, 0.00002, common)
        meta[f"MM{i}"] = ("Para Piyasası", f"MM PORTFÖY {i}. PARA PİYASASI FONU")
    for code in ("MA", "MB"):  # pazartesi deseni aynı, faizleri bağımsız
        prices[code] = mm_prices(rng, 0.0003)
        meta[code] = ("Para Piyasası", f"{code} PARA PİYASASI FONU")
    with Sm() as db:
        for code, (cat, name) in meta.items():
            db.add(Fund(code=code, name=name, category=cat, fund_type="YAT"))
            vol = 0.01 if code.startswith("M") else 0.2
            db.add(FundMetrics(fund_code=code, as_of=END, last_price=float(prices[code][-1]), volatility_1y=vol, data_points=250))
        # kapatılmış fon: verisi tam ama kümelemeye girmez
        db.add(Fund(code="KPL", name="KAPALI HİSSE SENEDİ FONU", category="Hisse Senedi", fund_type="YAT", status=STATUS_CLOSED))
        prices["KPL"] = prices["EQ0"] * 1.01
        db.add(Fund(code="YNI", name="YENİ HİSSE FONU", category="Hisse Senedi", fund_type="YAT"))  # 6 aylık
        prices["YNI"] = prices["EQ1"]
        db.add(Fund(code="ESK", name="ESKİ FON", category="Hisse Senedi", fund_type="YAT"))  # fiyatı 1 ay önce kesildi
        prices["ESK"] = prices["EQ2"]
        rows = []
        for code, p in prices.items():
            for d, v in zip(IDX, p):
                if code == "YNI" and d < pd.Timestamp("2026-05-01"):
                    continue
                if code == "ESK" and d > pd.Timestamp("2026-10-10"):
                    continue
                rows.append({"fund_code": code, "date": d.date(), "price": float(v)})
        db.execute(Price.__table__.insert(), rows)
        db.commit()
    return Sm


@pytest.fixture
def client(Session):
    def override():
        with Session() as s:
            yield s
    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def wide_of(db, codes=None):
    return S.load_wide(db, date(2024, 11, 1), END, codes)


def test_monday_effect_daily_vs_weekly(Session):
    """Faizleri bağımsız iki para piyasası fonu: günlük getiride pazartesi deseni yüzünden benzer, haftalıkta değil."""
    with Session() as db:
        w = wide_of(db, ["MA", "MB"])
    start = date(2025, 11, 13)
    assert S.daily_corr(w, start, END).loc["MA", "MB"] > 0.8
    assert abs(S.weekly_corr(w, start, END).loc["MA", "MB"]) < 0.4


def test_weekly_corr_groups_and_symmetry(Session):
    with Session() as db:
        w = wide_of(db, ["EQ0", "EQ1", "AU0", "MM0", "MM1"])
    C = S.weekly_corr(w, date(2025, 11, 13), END)
    assert np.allclose(C.to_numpy(), C.to_numpy().T, equal_nan=True)
    assert C.loc["EQ0", "EQ1"] > 0.85 and C.loc["MM0", "MM1"] > 0.85
    assert abs(C.loc["EQ0", "AU0"]) < 0.4


def test_weekly_corr_missing_overlap_is_nan():
    idx = pd.bdate_range("2025-11-01", END)
    rng = np.random.default_rng(3)
    a = pd.Series(np.cumprod(1 + rng.normal(0, 0.01, len(idx))), index=idx)
    b = a.copy()
    b[idx < pd.Timestamp("2026-08-01")] = np.nan  # yalnızca ~3,5 aylık ortak veri
    C = S.weekly_corr(pd.DataFrame({"A": a, "B": b}), date(2025, 11, 13), END)
    assert np.isnan(C.loc["A", "B"])


def test_coverage_and_missing_reasons(Session):
    with Session() as db:
        w = wide_of(db)
    ok = S.coverage_ok(w, date(2025, 11, 13), END)
    assert ok["EQ0"] and not ok["YNI"] and not ok["ESK"]
    assert S.missing_reason(w, "YNI", date(2025, 11, 13), END) == "1 yıllık fiyat verisi yok"
    assert S.missing_reason(w, "ESK", date(2025, 11, 13), END) == "son fiyatı eski"
    assert S.missing_reason(w, "YOK", date(2025, 11, 13), END) == "fiyat verisi yok"


def test_compute_recovers_groups_and_neighbors(Session):
    with Session() as db:
        r = S.compute(db)
    p = r["payload"]
    labels = {row["fund_code"]: row["cluster"] for row in r["clusters"]}
    assert "KPL" not in labels and "YNI" not in labels and "ESK" not in labels  # kapalı, kısa, eski
    codes = sorted(c for c in labels if not c.startswith("M") or c.startswith("MM"))
    truth = [c[:2] for c in codes]
    assert S.adjusted_rand([labels[c] for c in codes], truth) > 0.9
    assert p["k"] in S.K_RANGE and p["silhouette"] > 0.3
    assert p["stability"]["ari"] > 0.8  # gruplar iki yılda da aynı
    assert p["monday_effect"]["daily"] > p["monday_effect"]["weekly"]
    names = {c["name"] for c in p["clusters"]}
    assert "Altın ve kıymetli madenler" in names
    nb = [n for n in r["neighbors"] if n["fund_code"] == "EQ0"]
    assert [n["rank"] for n in nb] == [1, 2, 3, 4, 5]
    assert {n["neighbor_code"] for n in nb} == {"EQ1", "EQ2", "EQ3", "EQ4", "EQ5"}
    assert all(a["corr"] >= b["corr"] for a, b in zip(nb, nb[1:]))


def test_run_if_due_saves_and_replaces(Session):
    with Session() as db:
        first = S.run_if_due(db)
        assert "run_id" in first
        assert "skipped" in S.run_if_due(db)  # 28 gün dolmadı
        second = S.run_if_due(db, force=True)
        assert db.scalar(select(func.count()).select_from(SimilarityRun)) == 2
        # yalnızca son hesabın satırları tutulur
        assert set(db.scalars(select(FundCluster.run_id))) == {second["run_id"]}
        assert set(db.scalars(select(FundNeighbor.run_id))) == {second["run_id"]}


def test_run_if_due_without_data():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        assert S.run_if_due(db) == {"skipped": "yeterli veri yok"}


def test_analyze_pairs_missing_and_score(Session):
    with Session() as db:
        a = S.analyze(db, ["eq0", "EQ1", "AU0", "MM0", "MM1", "YNI", "ESK", "XYZ"], weights=[1, 1, 2, 1, 1, 1, 1, 1])
    assert a["ok"] == ["EQ0", "EQ1", "AU0", "MM0", "MM1"]
    assert {m["code"]: m["reason"] for m in a["missing"]} == {
        "YNI": "1 yıllık fiyat verisi yok", "ESK": "son fiyatı eski", "XYZ": "fiyat verisi yok"}
    pairs = {(p["a"], p["b"]): p for p in a["pairs"]}
    assert set(pairs) == {("EQ0", "EQ1"), ("MM0", "MM1")}
    assert pairs[("MM0", "MM1")]["low_vol"] and not pairs[("EQ0", "EQ1")]["low_vol"]
    assert 2.0 < a["n_eff"] < 4.0  # 5 fon ama ikişer ikişer aynı
    assert len(a["matrix"]) == 5 and a["matrix"][0][0] == 1.0


def test_analyze_needs_two_funds(Session):
    with Session() as db:
        a = S.analyze(db, ["EQ0", "YNI"])
    assert a["ok"] == ["EQ0"] and a["matrix"] == [] and a["n_eff"] is None


# --- API ------------------------------------------------------------------------------------------

def test_api_before_and_after_run(client, Session):
    r = client.get("/api/funds/EQ0/similar").json()
    assert r["available"] is False and "hesaplanmadı" in r["reason"]
    assert client.get("/api/clusters").status_code == 404
    with Session() as db:
        S.run_if_due(db)
    r = client.get("/api/funds/eq0/similar").json()
    assert r["available"] and len(r["neighbors"]) == 5 and r["neighbors"][0]["code"].startswith("EQ")
    assert r["cluster"]["size"] == 6 and "tavsiye" in r["note"]
    r = client.get("/api/funds/YNI/similar").json()
    assert r["available"] is False and "1 yıllık" in r["reason"]
    assert client.get("/api/funds/YOKBOYLE/similar").status_code == 404
    c = client.get("/api/clusters").json()
    assert c["report"]["k"] >= 5 and c["report"]["clusters"]


def test_api_correlation(client):
    r = client.get("/api/correlation", params={"codes": "EQ0,EQ1,AU0", "weights": "0.5,0.25,0.25"})
    body = r.json()
    assert r.status_code == 200 and body["pairs"][0]["a"] == "EQ0" and body["threshold"] == 0.9
    assert body["names"]["EQ0"].startswith("EQ PORTFÖY") and body["n_eff"] is not None
    # aynı fon iki kez: ağırlıklar birleşir
    assert client.get("/api/correlation", params={"codes": "EQ0,EQ0,AU0", "weights": "1,1,2"}).json()["ok"] == ["EQ0", "AU0"]
    assert client.get("/api/correlation", params={"codes": "EQ0,AU0", "weights": "1"}).status_code == 422
    assert client.get("/api/correlation", params={"codes": "EQ0,AU0", "weights": "1,-1"}).status_code == 422
    assert client.get("/api/correlation", params={"codes": "EQ0,,AU0"}).status_code == 422
    assert client.get("/api/correlation", params={"codes": ",".join(f"F{i}" for i in range(30))}).status_code == 422
