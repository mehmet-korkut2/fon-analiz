"""TÜFE (TP.TUKFIY2025.GENEL, 2025=100) verisini TCMB EVDS'ten yükler, ardından reel getiriyi yeniden hesaplar.

    python -m scripts.tufe_yukle            # eksik ayları ekle (ilk çalıştırmada 2005'ten bugüne)
    python -m scripts.tufe_yukle --hepsi    # bütün seriyi yeniden al

API anahtarı backend/.env'deki EVDS_API_KEY'den okunur; ekrana ya da günlüğe yazılmaz. Gece güncellemesi yeni ayları
kendisi ekler (TÜİK TÜFE'yi genellikle sonraki ayın 3'ünde açıklar); bu komut ilk yükleme ve deneme içindir.
"""
import argparse
import sys

from app.database import SessionLocal, init_db
from app.services import inflation, metrics_job


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TÜFE verisini EVDS'ten yükle")
    ap.add_argument("--hepsi", action="store_true", help="Bütün seriyi yeniden al")
    args = ap.parse_args(argv)
    init_db()
    with SessionLocal() as db:
        r = inflation.update(db, force=True) if args.hepsi or inflation.latest_month(db) is None else inflation.update(db)
        st = r["status"]
        if st == "anahtar_yok":
            print("EVDS API anahtarı tanımlı değil: backend/.env dosyasına EVDS_API_KEY= satırını ekleyin.", file=sys.stderr)
            return 1
        if st == "hata":
            print(f"TÜFE alınamadı: {r.get('error')}", file=sys.stderr)
            return 1
        s = inflation.status(db)
        print(f"Durum: {st}; {s['months']} ay, son ay {inflation.month_label(s['last_month']) if s['last_month'] else '-'} "
              f"({inflation.SERIES}, {inflation.BASE_YEAR}).")
        m = metrics_job.recompute_all(db)
        print(f"Metrikler yeniden hesaplandı; 1 yıllık reel getirisi olan fon: {m.get('real_1y', 0)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
