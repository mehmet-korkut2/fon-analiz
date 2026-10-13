"""TEFAS'tan fon listesini ve fiyat geçmişini çekip veritabanına yazar.

Örnekler (backend klasöründe, .venv aktifken):
    python -m scripts.tefas_yukle --limit 10            # ilk 10 fon, son 5 yıl
    python -m scripts.tefas_yukle --limit 0             # tüm fonlar, son 5 yıl (~15 dk)
    python -m scripts.tefas_yukle --fon TTE --ay 60     # tek fon, son 5 yıl
    python -m scripts.tefas_yukle --tip EMK --limit 20  # emeklilik fonları

Aynı veri iki kez yazılmaz; sadece eksik tarihler eklenir.
"""
import argparse
import logging

from app.database import init_db
from app.services.updater import run_update

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    ap = argparse.ArgumentParser(description="TEFAS verilerini veritabanına yükler")
    ap.add_argument("--tip", default="YAT", choices=["YAT", "EMK", "BYF"])
    ap.add_argument("--fon", help="Sadece bu fon kodu (ör. TTE)")
    ap.add_argument("--limit", type=int, default=10, help="En fazla kaç fon (0 = hepsi)")
    ap.add_argument("--ay", type=int, default=60, help="Kaç aylık geçmiş (1, 3, 6, 12, 36, 60). Varsayılan 5 yıl.")
    args = ap.parse_args()

    init_db()
    r = run_update(fund_type=args.tip, months=args.ay, limit=args.limit, only_code=args.fon)
    print(f"\nDurum: {r.status} | fon: {r.funds_updated}/{r.funds_total} | yeni fiyat: {r.new_prices} | hata: {len(r.errors)}")
    for e in r.errors[:10]:
        print("  -", e)


if __name__ == "__main__":
    main()
