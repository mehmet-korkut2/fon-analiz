"""SPK Bülteni 2026/60 kapsamındaki fonları işaretler (fiyat verisine dokunmaz).

    python -m scripts.fon_durumu_isaretle             # TEFAS'ı kontrol et, işaretle
    python -m scripts.fon_durumu_isaretle --deneme    # sadece raporla, veritabanına yazma
    python -m scripts.fon_durumu_isaretle --tefassiz  # TEFAS'a bağlanmadan sadece ada göre işaretle

Tera, Pusula, Hedef, Atlas, A1 Capital, Pardus ve Bulls Portföy'ün fonları adlarına göre bulunur:
- bültenin tasfiye listesinde unvanı geçenler -> islem_kapali_tasfiye
- diğerleri (TEFAS'taki tüm fonları alım satıma kapatıldı) -> islem_kapali
Önce TEFAS fon listesindeki tefasDurum alanına bakılır; false gelen fonun is_active'i de kapatılır.
"""
import argparse
from collections import Counter

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Fund
from app.services.fund_status import (
    STATUS_CLOSED,
    STATUS_LIQUIDATION,
    apply_status_rules,
    liquidation_keys,
    match_company,
    name_key,
)
from app.services.tefas_client import TefasClient, TefasError


def check_tefas_status(db) -> Counter:
    """7 şirketin fonları için TEFAS'taki tefasDurum değerlerini sayar; false olanları pasifleştirir."""
    seen = Counter()
    client = TefasClient()
    for tip in ("YAT", "EMK", "BYF"):
        try:
            listed = client.list_funds(tip)
        except TefasError as e:
            print(f"  {tip} listesi alınamadı: {e}")
            continue
        for f in listed:
            if not match_company(f.name):
                continue
            durum = f.raw.get("tefasDurum")
            seen[repr(durum)] += 1
            if durum is False:
                fund = db.get(Fund, f.code)
                if fund is not None:
                    fund.is_active = False
    return seen


def main():
    ap = argparse.ArgumentParser(description="SPK 2026/60 kapsamındaki fonları işaretler")
    ap.add_argument("--deneme", action="store_true", help="Veritabanına yazmadan raporla")
    ap.add_argument("--tefassiz", action="store_true", help="TEFAS'taki tefasDurum kontrolünü atla")
    args = ap.parse_args()

    init_db()
    with SessionLocal() as db:
        if not args.tefassiz:
            print("TEFAS'taki tefasDurum (7 şirketin fonları):")
            seen = check_tefas_status(db)
            print(f"  {dict(seen) or 'fon bulunamadı'}")
            if "False" not in seen:
                print("  Hiçbiri false değil; işaretleme sadece fon adına göre yapılacak.")

        counts = apply_status_rules(db, commit=False)
        by_company = {}
        for (company, status), n in counts.items():
            by_company.setdefault(company, Counter())[status] += n
        print("\nŞirket          tasfiye  sadece kapalı")
        for company, c in sorted(by_company.items()):
            print(f"  {company:<12} {c[STATUS_LIQUIDATION]:>7}  {c[STATUS_CLOSED]:>13}")
        total = Counter()
        for c in by_company.values():
            total.update(c)
        print(f"  {'Toplam':<12} {total[STATUS_LIQUIDATION]:>7}  {total[STATUS_CLOSED]:>13}")

        db_keys = {name_key(n) for n in db.scalars(select(Fund.name)) if n}
        missing = len(liquidation_keys() - db_keys)
        print(f"\nTasfiye listesinde {len(liquidation_keys())} fon var; {missing} tanesi veritabanında yok "
              "(büyük ihtimalle TEFAS fon listesinde yer almayan serbest fonlar).")

        if args.deneme:
            db.rollback()
            print("\nDeneme: veritabanına yazılmadı.")
        else:
            db.commit()
            print("\nKaydedildi. Metrikler için: python -m scripts.metrik_hesapla")


if __name__ == "__main__":
    main()
