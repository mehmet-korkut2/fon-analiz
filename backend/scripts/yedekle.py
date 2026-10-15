"""Veritabanının tarihli yedeğini proje kökündeki backups/ klasörüne alır.

Fon verisi, metrikler, tahminler, sanal portföy ve son bilinen döviz kurları dahil (tek dosya).
Backend çalışırken de güvenle alınabilir.

    python -m scripts.yedekle                     # backups/fon_2026-10-15_142530.db
    python -m scripts.yedekle --not sunum-oncesi  # backups/fon_2026-10-15_142530_sunum-oncesi.db
"""
import argparse

from app.services import yedek


def main():
    ap = argparse.ArgumentParser(description="Veritabanı yedeği al")
    ap.add_argument("--not", dest="label", help="Dosya adına eklenecek kısa not (ör. sunum-oncesi)")
    args = ap.parse_args()
    try:
        out = yedek.backup(label=args.label)
    except yedek.YedekHata as e:
        raise SystemExit(f"Yedek alınamadı: {e}")
    info = yedek.check(out)
    c = info["counts"]
    print(f"Yedek alındı: {out}")
    print(f"  {out.stat().st_size / 1e6:.1f} MB · {c.get('funds', 0)} fon · {c.get('prices', 0):,} fiyat · "
          f"{c.get('sanal_emirler', 0)} sanal emir · son fiyat {info['latest_price_date']}".replace(",", "."))


if __name__ == "__main__":
    main()
