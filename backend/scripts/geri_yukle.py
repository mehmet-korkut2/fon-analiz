"""Bir yedeği veritabanının yerine koyar. Varsayılan: backups/ içindeki en son yedek.

Önce mevcut veritabanının güvenlik kopyası alınır (backups/geri_yukleme_oncesi_*.db).
Backend çalışıyorsa önce durdurun (FonAnaliz_Durdur.bat); yoksa --zorla gerekir.

    python -m scripts.geri_yukle --liste                       # yedekleri listele
    python -m scripts.geri_yukle                               # en son yedeği geri yükle
    python -m scripts.geri_yukle fon_2026-10-15_142530.db      # seçilen yedeği geri yükle
"""
import argparse
from pathlib import Path

from app.services import yedek


def describe(p: Path) -> str:
    try:
        info = yedek.check(p)
        c = info["counts"]
        return f"{c.get('funds', 0)} fon, son fiyat {info['latest_price_date']}, {c.get('sanal_emirler', 0)} sanal emir"
    except yedek.YedekHata as e:
        return f"GEÇERSİZ: {e}"


def main():
    ap = argparse.ArgumentParser(description="Yedekten geri yükle")
    ap.add_argument("dosya", nargs="?", help="Yedek dosyası (adı ya da yolu); boşsa en son yedek")
    ap.add_argument("--liste", action="store_true", help="Yedekleri listele, geri yükleme")
    ap.add_argument("--zorla", action="store_true", help="Backend çalışıyor olsa da geri yükle")
    args = ap.parse_args()

    backups = yedek.list_backups()
    if args.liste:
        if not backups:
            print(f"{yedek.BACKUP_DIR} içinde yedek yok.")
        for p in backups:
            print(f"  {p.name}  ({p.stat().st_size / 1e6:.1f} MB; {describe(p)})")
        return

    if args.dosya:
        src = Path(args.dosya)
        if not src.is_file():
            src = yedek.BACKUP_DIR / args.dosya
    elif backups:
        src = backups[-1]
    else:
        raise SystemExit(f"{yedek.BACKUP_DIR} içinde yedek yok. Önce: python -m scripts.yedekle")

    if yedek.backend_running() and not args.zorla:
        raise SystemExit("Backend çalışıyor görünüyor (port 8000). Önce FonAnaliz_Durdur.bat ile durdurun "
                         "ya da --zorla ile devam edin.")
    try:
        safety = yedek.restore(src)
    except yedek.YedekHata as e:
        raise SystemExit(f"Geri yüklenemedi: {e}")
    print(f"Geri yüklendi: {src.name} -> {yedek.db_file()}")
    print(f"  {describe(yedek.db_file())}")
    if safety:
        print(f"  Önceki veritabanının kopyası: {safety}")


if __name__ == "__main__":
    main()
