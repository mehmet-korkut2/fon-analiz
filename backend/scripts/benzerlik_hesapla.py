"""Benzer fonları ve kümeleri yeniden hesaplar (app/ml/similarity.py).

    python -m scripts.benzerlik_hesapla

Gece güncellemesi bunu 28 günde bir kendisi yapar; bu komut ilk hesap ve deneme içindir (~10 sn).
"""
import sys

from app.database import SessionLocal, init_db
from app.ml import similarity


def main(argv: list[str] | None = None) -> int:
    init_db()
    with SessionLocal() as db:
        r = similarity.run_if_due(db, force=True)
        if "skipped" in r:
            print(f"Hesaplanmadı: {r['skipped']}", file=sys.stderr)
            return 1
        p = similarity.latest_run(db).payload
    st = p.get("stability") or {}
    print(f"{p['n_funds']} fon, {p['k']} küme (Ward, haftalık getiri korelasyonu), silhouette {p['silhouette']:.3f}")
    print(f"Kategorilerle örtüşme (ARI): bütün fonlar {p['ari_category']:.2f}, "
          f"varlık türünü belirten kategoriler {p['ari_homogeneous']:.2f}")
    if st:
        print(f"Kararlılık (önceki yılın kümeleriyle ARI): {st['ari']:.2f}; korelasyonun kalıcılığı {st['corr_persistence']:.2f}, "
              f"getirinin kalıcılığı {st['return_persistence']:.2f} (Spearman)")
    for c in p["clusters"]:
        print(f"  {c['id']:>2}. {c['name']} ({c['size']} fon, temsilci {c['representative']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
