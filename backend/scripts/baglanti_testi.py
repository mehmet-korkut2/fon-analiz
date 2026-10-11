"""Veri kaynaklarına ulaşılabildiğini kontrol eder ve örnek veriyi ekrana basar.

Çalıştırma (backend klasöründe, .venv aktifken):
    python -m scripts.baglanti_testi
"""
import json

from app.services import fx
from app.services.tefas_client import TefasClient, TefasError


def baslik(metin):
    print("\n" + "=" * 60 + f"\n{metin}\n" + "=" * 60)


def tefas_testi():
    baslik("1) TEFAS fon listesi")
    client = TefasClient(retries=1)
    try:
        funds = client.list_funds("YAT")
    except TefasError as e:
        print("HATA:", e)
        return
    print(f"{len(funds)} yatırım fonu bulundu.")
    if not funds:
        return
    print("İlk fonun TEFAS'tan gelen tüm alanları (keşif için):")
    print(json.dumps(funds[0].raw, ensure_ascii=False, indent=2)[:1500])
    for f in funds[:5]:
        print(f"  {f.code:6} {f.category or '-':30} {f.name}")

    kod = funds[0].code
    baslik(f"2) {kod} fonunun son 1 aylık fiyatları")
    prices = client.price_history(kod, months=1)
    print(f"{len(prices)} fiyat kaydı.")
    for p in prices[-5:]:
        print(f"  {p.date}  {p.price:.6f}")


def fx_testi():
    for kaynak in ("tcmb", "canli"):
        baslik(f"3) Döviz kurları: {kaynak}")
        try:
            sonuc = fx.get_rates(kaynak, use_cache=False)
        except fx.FxError as e:
            print("HATA:", e)
            continue
        print(f"Kaynak: {sonuc['source_name']}  Güncelleme: {sonuc['updated_at']}  Kayıt: {len(sonuc['rates'])}")
        for r in sonuc["rates"][:8]:
            print(f"  {r['code']:12} alış {r['buying']!s:>12}  satış {r['selling']!s:>12}  değişim {r['change']}")


if __name__ == "__main__":
    tefas_testi()
    fx_testi()
