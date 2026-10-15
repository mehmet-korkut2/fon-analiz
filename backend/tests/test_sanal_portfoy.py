from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Fund, Price, SanalDeger
from app.services import sanal_portfoy as S
from app.services.fund_status import STATUS_CLOSED

LAST = date(2026, 10, 9)  # cuma; veritabanındaki son fiyat günü
IDX = pd.bdate_range("2025-01-01", LAST)
MON, TUE, WED, THU, FRI = (date(2026, 10, d) for d in (12, 13, 14, 15, 16))


def hsa_price(i: int) -> float:
    return round(1.0 + 0.001 * i, 6)  # her iş günü 0,001 TL artar


def pp_price(i: int, rate: float) -> float:
    return 1.0 * (1 + rate) ** i


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        s.add_all([
            Fund(code="HSA", name="ÖRNEK HİSSE FONU", category="Hisse Senedi", risk_level=6, fund_type="YAT",
                 buy_valor=1, sell_valor=2, cutoff_time="17:45"),
            Fund(code="PPA", name="ÖRNEK PARA PİYASASI", category="Para Piyasası", risk_level=1, fund_type="YAT",
                 buy_valor=0, sell_valor=0, cutoff_time="13:30"),
            Fund(code="PPB", name="İKİNCİ PARA PİYASASI", category="Para Piyasası", risk_level=1, fund_type="YAT",
                 buy_valor=0, sell_valor=0, cutoff_time="13:30"),
            Fund(code="NOV", name="VALÖRSÜZ FON", category="Değişken", risk_level=4, fund_type="YAT"),
            Fund(code="CLS", name="KAPATILAN FON", category="Değişken", risk_level=5, fund_type="YAT",
                 status=STATUS_CLOSED, status_note="SPK kararıyla işleme kapatıldı.", buy_valor=1, sell_valor=1),
            Fund(code="OLD", name="ESKİ VERİLİ FON", category="Değişken", risk_level=4, fund_type="YAT", buy_valor=1),
        ])
        for i, d in enumerate(IDX):
            d = d.date()
            s.add_all([
                Price(fund_code="HSA", date=d, price=hsa_price(i)),
                Price(fund_code="PPA", date=d, price=pp_price(i, 0.0012)),
                Price(fund_code="PPB", date=d, price=pp_price(i, 0.0010)),
                Price(fund_code="NOV", date=d, price=2.0),
                Price(fund_code="CLS", date=d, price=1.5),
            ])
            if d <= date(2026, 9, 1):
                s.add(Price(fund_code="OLD", date=d, price=3.0))
        s.commit()
        S.settings(s, today=MON)
        yield s


def add_day(db, d: date, prices: dict[str, float] | None = None):
    """Gece güncellemesi gibi: yeni günün fiyatlarını ekler."""
    i = len(IDX) + int(np.busday_count(np.datetime64(LAST + timedelta(days=1)), np.datetime64(d)))
    prices = prices or {"HSA": hsa_price(i), "PPA": pp_price(i, 0.0012), "PPB": pp_price(i, 0.0010), "NOV": 2.0}
    db.add_all(Price(fund_code=c, date=d, price=p) for c, p in prices.items())
    db.commit()
    return prices


# --- İş günü ve valör ----------------------------------------------------------------

def test_order_day_weekend_and_cutoff():
    assert S.order_day(datetime(2026, 10, 14, 10, 0), "17:45") == WED
    assert S.order_day(datetime(2026, 10, 14, 18, 0), "17:45") == THU  # saat sonrası: ertesi iş günü
    assert S.order_day(datetime(2026, 10, 16, 18, 0), "17:45") == date(2026, 10, 19)  # cuma akşamı: pazartesi
    assert S.order_day(datetime(2026, 10, 17, 10, 0), "17:45") == date(2026, 10, 19)  # cumartesi
    assert S.order_day(datetime(2026, 10, 18, 10, 0), None) == date(2026, 10, 19)  # pazar


def test_target_date_valor_and_forward_pricing():
    assert S.target_date(MON, 1, LAST) == TUE
    assert S.target_date(FRI, 1, LAST) == date(2026, 10, 19)  # hafta sonu atlanır
    assert S.target_date(MON, 3, LAST) == THU
    # valör 0 ama o günün fiyatı zaten biliniyor: ileri fiyat, sonraki iş günü
    assert S.target_date(LAST, 0, LAST) == MON
    assert S.target_date(MON, 0, LAST) == MON


# --- Alış ----------------------------------------------------------------------------

def test_buy_waits_for_valor_then_executes_at_that_days_price(db):
    o = S.place_buy(db, "HSA", 10_000, now=datetime(2026, 10, 12, 10, 0))
    assert (o.status, o.order_date, o.valor, o.target_date) == (S.BEKLIYOR, MON, 1, TUE)
    st = S.state(db)
    assert st.reserved == 10_000 and st.available == 90_000 and st.cash == 100_000

    add_day(db, MON)  # pazartesi fiyatı geldi; hedef salı, hâlâ bekliyor
    assert S.process(db)["executed"] == 0
    tue = add_day(db, TUE)
    assert S.process(db)["executed"] == 1
    db.refresh(o)
    price = tue["HSA"]
    assert o.status == S.GERCEKLESTI and o.exec_date == TUE and o.exec_price == pytest.approx(price)
    assert o.exec_units == int(10_000 // price)  # tam pay; artan nakde döner
    st = S.state(db)
    assert st.reserved == 0 and st.cash == pytest.approx(100_000 - o.exec_units * price, abs=0.01)
    assert st.positions["HSA"].units == o.exec_units


def test_holiday_uses_next_trading_day_price(db):
    o = S.place_buy(db, "HSA", 5_000, now=datetime(2026, 10, 12, 10, 0))  # hedef salı
    add_day(db, MON)
    wed = add_day(db, WED)  # salı tatil: fiyat yok
    S.process(db)
    db.refresh(o)
    assert o.exec_date == WED and o.exec_price == pytest.approx(wed["HSA"])


def test_missing_valor_uses_next_business_day(db):
    o = S.place_buy(db, "NOV", 1_000, now=datetime(2026, 10, 12, 10, 0))
    assert o.valor_known is False and o.valor == 1 and o.target_date == TUE and "valör bilgisi yok" in o.note


def test_after_cutoff_counts_as_next_day(db):
    o = S.place_buy(db, "PPA", 1_000, now=datetime(2026, 10, 12, 14, 0))  # PPA son işlem 13:30, valör 0
    assert o.order_date == TUE and o.target_date == TUE


def test_insufficient_cash_counts_pending_buys(db):
    S.place_buy(db, "HSA", 70_000, now=datetime(2026, 10, 12, 10, 0))
    with pytest.raises(S.SanalHata, match="Yetersiz nakit"):
        S.place_buy(db, "PPA", 40_000, now=datetime(2026, 10, 12, 10, 0))
    S.place_buy(db, "PPA", 30_000, now=datetime(2026, 10, 12, 10, 0))  # tam kalan nakit
    assert S.state(db).available == pytest.approx(0)


def test_cannot_buy_closed_stale_or_bad_amount(db):
    with pytest.raises(S.SanalHata, match="işleme kapatıldı"):
        S.place_buy(db, "CLS", 1_000)
    with pytest.raises(S.SanalHata, match="güncellenmiyor"):
        S.place_buy(db, "OLD", 1_000)
    with pytest.raises(S.SanalHata, match="sıfırdan büyük"):
        S.place_buy(db, "HSA", 0)
    with pytest.raises(S.SanalHata, match="en az 1 pay"):
        S.place_buy(db, "NOV", 1.5)  # fiyat 2 TL
    with pytest.raises(S.SanalHata, match="bulunamadı"):
        S.place_buy(db, "YOK", 1_000)


# --- Satış -----------------------------------------------------------------------------

def _bought(db) -> int:
    S.place_buy(db, "HSA", 10_000, now=datetime(2026, 10, 12, 10, 0))
    add_day(db, MON)
    add_day(db, TUE)
    S.process(db)
    return S.state(db).positions["HSA"].units


def test_partial_sell_with_valor_and_average_cost(db):
    units = _bought(db)
    cost = S.state(db).positions["HSA"].cost
    half = units // 2
    o = S.place_sell(db, "HSA", half, now=datetime(2026, 10, 13, 20, 0))  # salı akşamı: çarşamba + 2 = cuma
    assert (o.order_date, o.valor, o.target_date) == (WED, 2, FRI)
    # bekleyen satıştaki paylar yeniden satılamaz
    with pytest.raises(S.SanalHata, match="satılabilir pay"):
        S.place_sell(db, "HSA", units - half + 1)
    assert S.state(db).sellable("HSA") == units - half

    add_day(db, WED)
    add_day(db, THU)
    S.process(db)
    db.refresh(o)
    assert o.status == S.BEKLIYOR  # satış valörü 2: cuma fiyatı bekleniyor
    fri = add_day(db, FRI)
    S.process(db)
    db.refresh(o)
    assert o.status == S.GERCEKLESTI and o.exec_amount == pytest.approx(half * fri["HSA"], abs=0.01)
    p = S.state(db).positions["HSA"]
    assert p.units == units - half
    assert p.cost == pytest.approx(cost * (units - half) / units)  # ortalama maliyet
    assert p.realized == pytest.approx(half * fri["HSA"] - cost * half / units, abs=0.01)


def test_sell_all_and_validation(db):
    units = _bought(db)
    with pytest.raises(S.SanalHata, match="tam sayı"):
        S.place_sell(db, "HSA", 0)
    with pytest.raises(S.SanalHata, match="satılabilir pay"):
        S.place_sell(db, "PPA", 1)  # hiç alınmamış
    S.place_sell(db, "HSA", units, now=datetime(2026, 10, 13, 20, 0))
    for d in (WED, THU, FRI):
        add_day(db, d)
    S.process(db)
    st = S.state(db)
    assert st.positions["HSA"].units == 0 and st.sellable("HSA") == 0
    assert st.cash > 100_000  # fiyat yükseldi; kâr nakde geçti


def test_cancel_releases_reserved_cash(db):
    o = S.place_buy(db, "HSA", 60_000, now=datetime(2026, 10, 12, 10, 0))
    S.cancel(db, o.id)
    assert S.state(db).available == 100_000 and o.status == S.IPTAL
    with pytest.raises(S.SanalHata, match="bekleyen"):
        S.cancel(db, o.id)


def test_reset_clears_orders_and_sets_balance(db):
    _bought(db)
    S.reset(db, 250_000, today=WED)
    st = S.state(db)
    assert st.cash == 250_000 and not st.positions and S.settings(db).start_date == WED
    with pytest.raises(S.SanalHata, match="arasında"):
        S.reset(db, 10)


# --- Değer geçmişi ve kıyas ---------------------------------------------------------------

def test_value_history_and_money_market_benchmark(db):
    units = _bought(db)
    rows = list(db.scalars(select(SanalDeger).order_by(SanalDeger.date)))
    assert [r.date for r in rows] == [MON, TUE]
    first, last = rows[0], rows[-1]
    assert first.total == 100_000 and first.benchmark == pytest.approx(100_000)
    o = S.orders(db, S.GERCEKLESTI)[0]
    assert last.holdings == pytest.approx(units * o.exec_price, abs=0.01)
    assert last.total == pytest.approx(last.cash + last.holdings, abs=0.01)
    # kıyas: PPA ve PPB'nin pazartesiden salıya getirilerinin medyanı
    expected = np.median([1.0012, 1.0010]) * 100_000
    assert last.benchmark == pytest.approx(expected, rel=1e-6)
    out = S.summary(db)
    assert out["total"] == pytest.approx(last.total, abs=0.01) and out["positions"][0]["code"] == "HSA"
    assert out["pnl"] == pytest.approx(out["total"] - 100_000, abs=0.01)


# --- "Ya o zaman alsaydım?" ----------------------------------------------------------------

def test_what_if_buys_on_first_trading_day_after_date(db):
    out = S.what_if(db, ["HSA"], date(2025, 1, 4), 10_000)  # cumartesi: pazartesi fiyatı
    f = out["funds"][0]
    assert f["buy_date"] == date(2025, 1, 6) and f["buy_price"] == pytest.approx(hsa_price(3))
    assert f["last_date"] == LAST
    assert f["value"] == pytest.approx(10_000 * hsa_price(len(IDX) - 1) / hsa_price(3), abs=0.01)
    assert f["pnl_pct"] == pytest.approx(f["value"] / 10_000 - 1, abs=1e-6)
    days = (LAST - date(2025, 1, 6)).days
    assert f["annualized"] == pytest.approx((1 + f["pnl_pct"]) ** (365.25 / days) - 1)
    # para piyasası medyanı aynı dönemde
    n = len(IDX) - 1 - 3
    assert f["mm_pct"] == pytest.approx(np.median([1.0012 ** n, 1.0010 ** n]) - 1, rel=1e-6)
    assert out["series"][-1]["HSA"] == pytest.approx(f["value"], abs=0.01) and "mm" in out["series"][-1]


def test_what_if_short_period_not_annualized_and_compare(db):
    out = S.what_if(db, ["HSA", "PPA", "CLS"], date(2026, 6, 1), 1_000)
    assert [f["code"] for f in out["funds"]] == ["HSA", "PPA", "CLS"]
    assert all(f["annualized"] is None for f in out["funds"])  # 1 yıldan kısa
    assert out["funds"][1]["pnl_pct"] > 0 and out["funds"][2]["status"] == STATUS_CLOSED


def test_what_if_validation(db):
    with pytest.raises(S.SanalHata, match="En fazla 4"):
        S.what_if(db, ["HSA", "PPA", "PPB", "NOV", "CLS"], date(2026, 1, 5), 1_000)
    with pytest.raises(S.SanalHata, match="son fiyat gününden"):
        S.what_if(db, ["HSA"], LAST, 1_000)
    with pytest.raises(S.SanalHata, match="başlıyor"):
        S.what_if(db, ["HSA"], date(2020, 1, 1), 1_000)


def test_api(db):
    def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        c = TestClient(app)
        body = c.get("/api/sanal-portfoy").json()
        assert body["total"] == 100_000 and body["positions"] == [] and body["values"]
        r = c.post("/api/sanal-portfoy/emir", json={"code": "CLS", "side": "alis", "amount": 1000})
        assert r.status_code == 400 and "işleme kapatıldı" in r.json()["detail"]
        r = c.post("/api/sanal-portfoy/emir", json={"code": "HSA", "side": "alis", "amount": 1000})
        assert r.status_code == 200 and len(r.json()["pending"]) == 1 and r.json()["reserved"] == 1000
        oid = r.json()["pending"][0]["id"]
        assert c.delete(f"/api/sanal-portfoy/emir/{oid}").json()["history"][0]["status"] == "iptal"
        assert c.post("/api/sanal-portfoy/sifirla", json={"initial_balance": 50_000}).json()["total"] == 50_000
        w = c.get("/api/sanal-portfoy/geriye", params={"funds": "HSA,PPA", "tarih": "2025-06-02", "tutar": 5000})
        assert w.status_code == 200 and len(w.json()["funds"]) == 2
        assert c.get("/api/sanal-portfoy/geriye", params={"funds": "HSA", "tarih": "2030-01-01"}).status_code == 400
        assert c.get("/api/funds/HSA").json()["sell_valor"] == 2
    finally:
        app.dependency_overrides.clear()


def test_annualized_threshold():
    assert S.annualized(0.10, 359) is None  # yaklaşık 1 yıldan kısa: yıllıklandırılmaz
    assert S.annualized(0.10, 365) == pytest.approx(1.10 ** (365.25 / 365) - 1)
    assert S.annualized(0.21, 730) == pytest.approx(0.10, abs=1e-3)
    assert S.annualized(-1.0, 400) is None
