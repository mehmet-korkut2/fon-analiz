"""Fiyat serilerinde şüpheli günlük sıçramaları listeler (veritabanını değiştirmez).

    python -m scripts.veri_kalitesi                    # tüm fonlar, eşik %30
    python -m scripts.veri_kalitesi --esik 0.2         # eşik %20
    python -m scripts.veri_kalitesi --fon TLY          # tek fon
    python -m scripts.veri_kalitesi --csv sicramalar.csv   # tüm listeyi dosyaya yaz
"""
import argparse

import pandas as pd
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Fund, Price
from app.services.data_quality import DEFAULT_THRESHOLD, find_jumps, summarize


def main():
    ap = argparse.ArgumentParser(description="Şüpheli fiyat sıçramalarını bulur")
    ap.add_argument("--esik", type=float, default=DEFAULT_THRESHOLD, help="Günlük değişim eşiği (0.30 = %%30)")
    ap.add_argument("--fon", help="Sadece bu fon kodu")
    ap.add_argument("--goster", type=int, default=40, help="Ekranda en fazla kaç sıçrama gösterilsin")
    ap.add_argument("--csv", help="Tüm sıçramaları bu CSV dosyasına yaz")
    args = ap.parse_args()

    with SessionLocal() as db:
        stmt = select(Price.fund_code, Price.date, Price.price)
        if args.fon:
            stmt = stmt.where(Price.fund_code == args.fon.upper())
        prices = pd.DataFrame(db.execute(stmt).all(), columns=["code", "date", "price"])
        names = dict(db.execute(select(Fund.code, Fund.name)).all())

    jumps = find_jumps(prices, args.esik)
    s = summarize(jumps, prices["code"].nunique())
    print(f"\nTaranan fon: {s['funds_scanned']} | fiyat: {len(prices):,} | eşik: %{args.esik * 100:g}")
    print(f"Sıçrama olan fon: {s['funds_with_jumps']} | sıçrama: {s['jumps']} "
          f"(tek günlük hata, giriş+dönüş: {s['reverted']}, kalıcı: {s['persistent']})")
    if jumps.empty:
        return

    print("\nFon başına:")
    per_fund = jumps.groupby("code").agg(adet=("change", "size"), en_buyuk=("change", lambda c: c.loc[c.abs().idxmax()]),
                                         geri_donen=("reverted", "sum")).sort_values("adet", ascending=False)
    for code, r in per_fund.iterrows():
        print(f"  {code:<6} {int(r.adet):>3} sıçrama, en büyüğü {r.en_buyuk:+.0%}, geri dönen {int(r.geri_donen)}  {names.get(code, '')[:60]}")

    print(f"\nEn büyük {min(args.goster, len(jumps))} sıçrama:")
    top = jumps.reindex(jumps["change"].abs().sort_values(ascending=False).index).head(args.goster)
    for r in top.itertuples():
        nxt = f"{r.next_price:,.6f}" if pd.notna(r.next_price) else "–"
        flag = "geri döndü" if r.reverted else "kalıcı"
        print(f"  {r.code:<6} {r.prev_date} {r.prev_price:>14,.6f} -> {r.date} {r.price:>14,.6f}  {r.change:+8.1%}  ertesi gün {nxt}  [{flag}]")

    if args.csv:
        jumps.assign(name=jumps["code"].map(names)).to_csv(args.csv, index=False, encoding="utf-8-sig")
        print(f"\nTüm liste: {args.csv}")


if __name__ == "__main__":
    main()
