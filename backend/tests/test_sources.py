"""Veri kaynağı ayrıştırıcılarının testleri. İnternete çıkmaz, örnek yanıtlar kullanır."""
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.services import fx
from app.services.tefas_client import parse_fund_list, parse_kap_link, parse_prices, parse_profile, parse_snapshot, snap_period

TCMB_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date Tarih="09.10.2026" Date="10/09/2026" Bulten_No="2026/191">
  <Currency CrossOrder="0" Kod="USD" CurrencyCode="USD">
    <Unit>1</Unit><Isim>ABD DOLARI</Isim><CurrencyName>US DOLLAR</CurrencyName>
    <ForexBuying>49.1274</ForexBuying><ForexSelling>49.2160</ForexSelling>
    <BanknoteBuying>49.0931</BanknoteBuying><BanknoteSelling>49.2898</BanknoteSelling>
    <CrossRateUSD/><CrossRateOther/>
  </Currency>
  <Currency CrossOrder="0" Kod="XDR" CurrencyCode="XDR">
    <Unit>1</Unit><Isim>ÖZEL ÇEKME HAKKI (SDR)</Isim>
    <ForexBuying>66.5644</ForexBuying><ForexSelling/><BanknoteBuying/><BanknoteSelling/>
  </Currency>
</Tarih_Date>"""

CANLI_JSON = {
    "Update_Date": "2026-10-11 11:14:01",
    "USD": {"Buying": 49.1432, "Type": "Currency", "Selling": 49.3979, "Change": 0.03},
    "EUR": {"Buying": "54,9452", "Type": "Currency", "Selling": "55,6494", "Change": "%-0,18"},
    "GRA": {"Selling": 6644.78, "Type": "Gold", "Name": "GRAMALTIN", "Change": 1.51, "Buying": 6643.95},
    "XU100": {"Buying": 10500.5, "Selling": 10500.5, "Type": "Index", "Change": -0.4},
}


def test_parse_tcmb():
    r = fx.parse_tcmb(TCMB_XML)
    assert r["updated_at"] == "09.10.2026"
    usd = r["rates"][0]
    assert usd["code"] == "USD" and usd["buying"] == 49.1274 and usd["banknote_selling"] == 49.2898
    assert r["rates"][1]["selling"] is None  # XDR'de satış yok


def test_parse_canli_handles_numbers_and_strings():
    r = fx.parse_canli(CANLI_JSON)
    by_code = {x["code"]: x for x in r["rates"]}
    assert by_code["USD"]["name"] == "ABD Doları"
    assert by_code["EUR"]["buying"] == 54.9452 and by_code["EUR"]["change"] == -0.18
    assert by_code["GRA"]["group"] == "altin"
    assert by_code["XU100"]["group"] == "diger"
    assert r["updated_at"] == "2026-10-11 11:14:01"


def test_fx_endpoint_uses_cache(monkeypatch):
    calls = []

    def fake_fetch(source):
        calls.append(source)
        return fx.parse_canli(CANLI_JSON)

    fx._cache.clear()
    monkeypatch.setattr(fx, "_fetch", fake_fetch)
    client = TestClient(app)
    assert client.get("/api/fx").status_code == 200
    body = client.get("/api/fx").json()
    assert len(calls) == 1  # ikinci istek önbellekten geldi
    assert body["source"] == "canli" and len(body["rates"]) == 4


def test_fx_endpoint_returns_503_when_source_down(monkeypatch):
    def broken(source):
        raise fx.FxError("bağlantı yok")

    fx._cache.clear()
    monkeypatch.setattr(fx, "_fetch", broken)
    r = TestClient(app).get("/api/fx?source=tcmb")
    assert r.status_code == 503


def test_parse_tefas_prices_skips_bad_rows():
    rows = [
        {"tarih": "2026-10-09", "fonKodu": "TTE", "fiyat": 1.25},
        {"tarih": "2026-10-08T00:00:00", "fonKodu": "TTE", "fiyat": "1,20"},
        {"tarih": None, "fonKodu": "TTE", "fiyat": 1.1},
        {"tarih": "2026-10-07", "fonKodu": "TTE", "fiyat": 0},
    ]
    prices = parse_prices(rows, "tte")
    assert [p.date for p in prices] == [date(2026, 10, 8), date(2026, 10, 9)]
    assert prices[0].price == 1.20


def test_parse_tefas_fund_list():
    # TEFAS'ın gerçek yanıtından alınmış örnek
    rows = [
        {"fonKodu": "AU1", "fonUnvan": "A1 CAPİTAL PORTFÖY ALTIN FONU",
         "fonTurAciklama": "Kıymetli Madenler Şemsiye Fonu", "tefasDurum": True,
         "getiri1a": -5.2234, "getiri1y": None, "riskDegeri": "6"},
        {"fonKodu": "xyz ", "fonUnvan": "Kapalı Fon", "tefasDurum": False, "riskDegeri": None},
        {"x": 1},
    ]
    funds = parse_fund_list(rows, "YAT")
    assert len(funds) == 2
    au1, xyz = funds
    assert au1.category == "Kıymetli Madenler" and au1.risk_level == 6 and au1.is_active
    assert xyz.code == "XYZ" and xyz.risk_level is None and not xyz.is_active


def test_snap_period():
    assert snap_period(2) == 3 and snap_period(12) == 12 and snap_period(100) == 60


def test_parse_tefas_snapshot():
    rows = [{"fonKodu": "TTE", "sonFiyat": 1.10794, "payAdet": 2048583509, "portBuyukluk": 2269708592.44,
             "yatirimciSayi": 39630, "kategoriDerece": 139}]
    s = parse_snapshot(rows, "tte")
    assert (s.code, s.total_value, s.investor_count, s.shares_outstanding) == ("TTE", 2269708592.44, 39630, 2048583509)
    s = parse_snapshot([{"fonKodu": "X", "portBuyukluk": None, "yatirimciSayi": ""}], "X")
    assert s.total_value is None and s.investor_count is None
    assert parse_snapshot([], "X") is None


def test_parse_kap_link_accepts_only_kap():
    ok = "https://www.kap.org.tr/tr/fon-bilgileri/genel/tte-is-portfoy"
    assert parse_kap_link([{"kapLink": ok}]) == ok
    assert parse_kap_link([{"kapLink": "javascript:alert(1)"}]) is None
    assert parse_kap_link([{"kapLink": "https://kap.org.tr.evil.com/x"}]) is None
    assert parse_kap_link([{"kapLink": None}]) is None and parse_kap_link([]) is None


def test_parse_profile_valor_mapping():
    # Yabancı hisse fonu: alış T+1, satış T+3. TEFAS'ta alış = fonGeriAlisValor, satış = fonSatisValor
    rows = [{"fonKodu": "GUH", "kapLink": "https://www.kap.org.tr/tr/fon-bilgileri/genel/guh", "fonSatisValor": 3,
             "fonGeriAlisValor": 1, "sonIsSaat": "17:45", "basIsSaat": "09:00"}]
    p = parse_profile(rows)
    assert (p.buy_valor, p.sell_valor, p.cutoff) == (1, 3, "17:45") and p.kap_url.endswith("/guh")
    p = parse_profile([{"fonSatisValor": None, "fonGeriAlisValor": "x", "sonIsSaat": "25:00"}])
    assert (p.buy_valor, p.sell_valor, p.cutoff, p.kap_url) == (None, None, None, None)
    assert parse_profile([]) is None
