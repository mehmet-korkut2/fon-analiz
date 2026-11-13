"""Veritabanının tarihli yedeğini proje kökündeki backups/ klasörüne alır.

Fon verisi, metrikler, tahminler, sanal portföy ve son bilinen döviz kurları dahil (tek dosya, gzip ile
sıkıştırılmış). Backend çalışırken de güvenle alınabilir.

    python -m scripts.yedekle                     # backups/fon_2026-10-15_142530.db.gz
    python -m scripts.yedekle --not sunum-oncesi  # backups/fon_2026-10-15_142530_sunum-oncesi.db.gz
    python -m scripts.yedekle --sikistirma        # sıkıştırmadan (.db)
"""
import argparse

from app.services import yedek


def main():
    ap = argparse.ArgumentParser(description="Veritabanı yedeği al")
    ap.add_argument("--not", dest="label", help="Dosya adına eklenecek kısa not (ör. sunum-oncesi)")
    ap.add_argument("--sikistirma", action="store_true", help="Sıkıştırmadan .db olarak al")
    args = ap.parse_args()
    try:
        r = yedek.backup_with_stats(label=args.label, compress=not args.sikistirma)
    except yedek.YedekHata as e:
        raise SystemExit(f"Yedek alınamadı: {e}")
    info = yedek.check(r.path)
    c = info["counts"]
    size = f"{dec(r.size_bytes / 1e6)} MB"
    if r.size_bytes != r.raw_bytes:
        size += f" (veritabanı {dec(r.raw_bytes / 1e6)} MB, sıkıştırılmış hali %{r.size_bytes / r.raw_bytes * 100:.0f})"
    print(f"Yedek alındı: {r.path}")
    print(f"  {size} · süre {dec(r.seconds)} sn")
    print(f"  {c.get('funds', 0)} fon · {thousands(c.get('prices', 0))} fiyat · {thousands(c.get('forecast_days', 0))} tahmin kaydı · "
          f"{c.get('sanal_emirler', 0)} sanal emir · son fiyat {info['latest_price_date']}")


def dec(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


if __name__ == "__main__":
    main()
