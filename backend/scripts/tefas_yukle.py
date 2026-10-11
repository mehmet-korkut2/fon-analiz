"""TEFAS'tan fon listesini ve fiyat geçmişini çekip veritabanına yazar.

Örnekler (backend klasöründe, .venv aktifken):
    python -m scripts.tefas_yukle --limit 10            # ilk 10 fon, son 12 ay
    python -m scripts.tefas_yukle --fon TTE --ay 60     # tek fon, son 5 yıl
    python -m scripts.tefas_yukle --tip EMK --limit 20  # emeklilik fonları

Aynı gün iki kez çalıştırılırsa sadece yeni tarihleri ekler.
"""
import argparse
import logging

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Fund, Price
from app.services.tefas_client import TefasClient, TefasError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tefas_yukle")


def upsert_funds(db, funds):
    for f in funds:
        fund = db.get(Fund, f.code)
        if fund is None:
            fund = Fund(code=f.code)
            db.add(fund)
        fund.name = f.name or fund.name or f.code
        fund.category = f.category or fund.category
        fund.fund_type = f.fund_type
        fund.risk_level = f.risk_level or fund.risk_level
        fund.is_active = f.is_active
    db.commit()


def save_prices(db, code, prices) -> int:
    existing = set(db.scalars(select(Price.date).where(Price.fund_code == code)))
    new = [Price(fund_code=code, date=p.date, price=p.price) for p in prices if p.date not in existing]
    db.add_all(new)
    db.commit()
    return len(new)


def main():
    ap = argparse.ArgumentParser(description="TEFAS verilerini veritabanına yükler")
    ap.add_argument("--tip", default="YAT", choices=["YAT", "EMK", "BYF"])
    ap.add_argument("--fon", help="Sadece bu fon kodu (ör. TTE)")
    ap.add_argument("--limit", type=int, default=10, help="En fazla kaç fon (0 = hepsi)")
    ap.add_argument("--ay", type=int, default=12, help="Kaç aylık geçmiş (1, 3, 6, 12, 36, 60)")
    args = ap.parse_args()

    Base.metadata.create_all(bind=engine)
    client = TefasClient()

    with SessionLocal() as db:
        funds = client.list_funds(args.tip)
        log.info("%s fon listelendi (%s).", len(funds), args.tip)
        if args.fon:
            funds = [f for f in funds if f.code == args.fon.upper()]
            if not funds:
                log.error("%s kodlu fon bulunamadı.", args.fon)
                return
        elif args.limit:
            funds = funds[: args.limit]
        upsert_funds(db, funds)

        toplam = 0
        for i, f in enumerate(funds, 1):
            try:
                prices = client.price_history(f.code, months=args.ay)
            except TefasError as e:
                log.error("%s atlandı: %s", f.code, e)
                continue
            eklenen = save_prices(db, f.code, prices)
            toplam += eklenen
            log.info("[%s/%s] %s: %s fiyat, %s yeni", i, len(funds), f.code, len(prices), eklenen)

    log.info("Bitti. Toplam %s yeni fiyat kaydı eklendi.", toplam)


if __name__ == "__main__":
    main()
