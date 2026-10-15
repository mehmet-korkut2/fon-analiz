"""Fonların güncel büyüklüğünü, yatırımcı sayısını ve KAP bağlantısını TEFAS'tan alır.

Gece güncellemesi bunu fiyatlarla birlikte zaten yapar; bu betik ilk doldurma veya
elle yenileme içindir. Fon başına 1-2 istek, istekler arasında TefasClient'ın beklemesi var
(~1.000 fon için ~15-25 dk).

    python -m scripts.fon_bilgisi_yukle            # TEFAS'ta işlem gören bütün fonlar
    python -m scripts.fon_bilgisi_yukle --fon TTE
"""
import argparse
import logging

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Fund
from app.services.tefas_client import TefasClient, TefasError
from app.services.updater import update_info

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main():
    ap = argparse.ArgumentParser(description="Fon büyüklüğü, yatırımcı sayısı ve KAP bağlantısı")
    ap.add_argument("--fon", help="Sadece bu fon kodu")
    args = ap.parse_args()

    init_db()
    client = TefasClient()
    with SessionLocal() as db:
        stmt = select(Fund.code).where(Fund.is_active.is_(True)).order_by(Fund.code)
        if args.fon:
            stmt = select(Fund.code).where(Fund.code == args.fon.upper())
        codes = list(db.scalars(stmt))
        ok, errors = 0, []
        for i, code in enumerate(codes, 1):
            try:
                ok += update_info(db, client, code)
            except TefasError as e:
                errors.append(f"{code}: {e}")
            if i % 100 == 0:
                log.info("[%s/%s] işlendi", i, len(codes))
    print(f"\nFon: {len(codes)} | büyüklüğü alınan: {ok} | hata: {len(errors)}")
    for e in errors[:10]:
        print("  -", e)


if __name__ == "__main__":
    main()
