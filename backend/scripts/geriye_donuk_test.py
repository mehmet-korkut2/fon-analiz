"""Kayan pencereli geriye dönük testi hesaplar, backtest_windows tablosuna yazar ve özeti basar.

    python -m scripts.geriye_donuk_test            # hesapla, kaydet, özet (~1 dk)
    python -m scripts.geriye_donuk_test --pencere  # her pencereyi de listele

Son 3 yılda her ayın ilk işlem günü, o güne kadarki veriyle her profil için örnek portföy seçilir;
sonraki 12 aydaki getirisi para piyasası fonlarının medyanıyla karşılaştırılır. Gece güncellemesi
de bunu otomatik yapar; bu betik ilk kurulum ve elle yenileme içindir.
"""
import argparse
import time

from app.database import SessionLocal, init_db
from app.services import recommender as R


def pct(v: float) -> str:
    return ("-" if v < -0.0005 else "") + f"%{abs(v) * 100:.1f}".replace(".", ",")


def signed(v: float) -> str:
    return ("+" if v >= 0 else "") + pct(v)


def main():
    ap = argparse.ArgumentParser(description="Kayan pencereli geriye dönük test")
    ap.add_argument("--pencere", action="store_true", help="Her pencereyi listele")
    args = ap.parse_args()

    init_db()
    t0 = time.time()
    with SessionLocal() as db:
        n = R.store_rolling(db)
        print(f"{n} pencere hesaplandı ({time.time() - t0:.0f} sn).\n")
        for qualified in (False, True):
            print(f"### {'Nitelikli yatırımcı (serbest fonlar dahil)' if qualified else 'Nitelikli olmayan yatırımcı'}\n")
            print("| Profil | Dönem | PP medyanını geçtiği | Ort. fazla getiri | Medyan fazla getiri | Ort. portföy / PP | En iyi dönem | En kötü dönem |")
            print("|---|---|---|---|---|---|---|---|")
            for profile in R.PROFILES_ALL:
                ws = R.load_windows(db, profile, qualified)
                s = R.summarize_windows(ws)
                if not s:
                    print(f"| {profile} | 0 | – | – | – | – | – | – |")
                    continue
                b, w = s["best"], s["worst"]
                print(f"| {profile} | {s['windows']} | {s['beats']}/{s['windows']} | {signed(s['mean_excess'])} | {signed(s['median_excess'])} | "
                      f"{pct(s['mean_portfolio'])} / {pct(s['mean_benchmark'])} | {b.start:%m.%Y}: {signed(b.excess)} | {w.start:%m.%Y}: {signed(w.excess)} |")
            print()
            if args.pencere:
                for profile in R.PROFILES_ALL:
                    print(f"{profile}:")
                    for w in R.load_windows(db, profile, qualified):
                        print(f"  {w.start} → {w.end}  {','.join(w.codes):<26} portföy {pct(w.portfolio_return):>7}  PP {pct(w.benchmark_return):>7}  fark {signed(w.excess):>8}")
                print()


if __name__ == "__main__":
    main()
