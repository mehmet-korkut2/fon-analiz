"""ML tahmin modülünün walk-forward değerlendirmesi. Çıktı markdown'dır.

    python -m scripts.ml_degerlendir > ../docs/ml_tahmin_cikti.md                  # ~2-3 dk
    python -m scripts.ml_degerlendir --ayar --arima > ../docs/ml_tahmin_cikti.md   # hiperparametre ayarı + ARIMA, ~7 dk
    python -m scripts.ml_degerlendir --arima --kaydet                              # sonucu ml_reports tablosuna da yaz
    python -m scripts.ml_degerlendir --kayittan > ../docs/ml_tahmin_cikti.md       # kayıtlı son raporu yazdır (hesaplamaz)

Hesaplamalar app/ml/report.py'de; takvim ve başarı ölçütü orada (sonuçlar görülmeden önce belirlendi).
--ayar olmadan, ayar döneminde seçilmiş BEST_PARAMS kullanılır.
"""
import argparse
import sys
import time

from app.database import SessionLocal, init_db
from app.ml.features import build_dataset, load_panel, month_starts
from app.ml.report import GROUP_LABELS, build_report

COLS = [("n", "Örnek"), ("mae", "MAE"), ("rmse", "RMSE"), ("mae_excess", "Fazla MAE"), ("rmse_excess", "Fazla RMSE"),
        ("dir_raw", "Ham yön"), ("dir_excess", "PP üstü/altı yönü"), ("ic", "Sıralama korel."), ("top10", "İlk 10 (aylık)"),
        ("coverage", "%80 aralık kapsamı")]


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def pct(v, d=2):
    return "–" if v is None else ("-" if v < 0 else "") + f"%{abs(v) * 100:.{d}f}".replace(".", ",")


def thousands(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def num(v, d=3):
    return "–" if v is None else f"{v:.{d}f}".replace(".", ",")


def cell(col, r):
    v = r.get(col)
    if col == "n":
        return f"{int(v):,}".replace(",", ".")
    if col == "ic":
        return num(v)
    if col == "dir_raw" and r.get("model") == "sifir":
        return "–"  # sıfır tahmini yön söylemez
    return pct(v, 1 if col in ("dir_raw", "dir_excess", "coverage") else 2)


def table(rows):
    cols = [c for c in COLS if any(c[0] in r for r in rows)]
    print("| Model | " + " | ".join(lbl for _, lbl in cols) + " |")
    print("|---|" + "---|" * len(cols))
    for r in rows:
        print(f"| {r['label']} | " + " | ".join(cell(c, r) for c, _ in cols) + " |")
    print()


def render(rep):
    c = rep["calendar"]
    print("# ML tahmin modülü: walk-forward değerlendirme çıktısı\n")
    print(f"Veri tarihi {rep['data_as_of']}. {c['origins']} aybaşı ({c['first']} – {c['last']}), {thousands(c['samples'])} örnek, "
          f"{c['funds']} fon. Hedef: {rep['horizon']} işlem günlük getiri.  ")
    print(f"Ayar dönemi: {c['valid'][2]} ay ({c['valid'][0]} – {c['valid'][1]}). Test dönemi: {c['test'][2]} ay "
          f"({c['test'][0]} – {c['test'][1]}), {thousands(c['test_samples'])} tahmin.\n")

    print("## 1. LightGBM hiperparametreleri (sadece ayar dönemi)\n")
    if rep["tuning"]:
        print("Seçim ölçütü: ayar dönemindeki aylık fazla getiri MAE'sinin ortalaması. En iyi 5 aday:\n")
        print("| num_leaves | min_child_samples | n_estimators | Fazla MAE |\n|---|---|---|---|")
        for r in rep["tuning"][:5]:
            print(f"| {r['num_leaves']} | {r['min_child_samples']} | {r['n_estimators']} | {pct(r['mae_excess'], 3)} |")
        print()
    print(f"Kullanılan: {rep['params']}; objective=l1, learning_rate=0,03, subsample=0,8, colsample=0,8.\n")

    print("## 2. Test dönemi: genel sonuçlar\n")
    print("MAE/RMSE ham getiri, \"Fazla\" PP medyanına göre fazla getiri üzerinden. Ham yön: getirinin işareti "
          "(getirilerin çoğu pozitif olduğundan yanıltıcı). PP üstü/altı yönü: fonun PP medyanını geçip geçmeyeceği. "
          "Sıralama korel.: ay içinde tahmin ve gerçekleşen fazla getirinin Spearman korelasyonu (ortalama). "
          "İlk 10: her ay tahmini en yüksek 10 fonun gerçekleşen ortalama getirisi.\n")
    table(rep["overall"])
    b = rep["benchmarks"]
    print(f"Kıyas: aynı aylarda tüm fonların ortalama getirisi {pct(b['universe'])}, PP medyanı {pct(b['mm'])}.\n")

    print("## 3. Risk grubuna göre\n")
    for g, rows in rep["groups"].items():
        print(f"### {GROUP_LABELS[g]} ({thousands(rows[0]['n'])} tahmin)\n")
        table(rows)

    print("## 4. Başarı ölçütü (risk grubu bazında)\n")
    print("| Risk grubu | En iyi referans | LightGBM fazla MAE | Referans fazla MAE | LightGBM ilk 10 | Referans ilk 10 | "
          "LightGBM'in daha iyi olduğu ay | Aylık MAE farkı (± std. hata) | Sonuç |\n|---|---|---|---|---|---|---|---|---|")
    for v in rep["verdicts"]:
        print(f"| {v['group_label']} | {v['reference_label']} | {pct(v['model_mae_excess'], 3)} | {pct(v['reference_mae_excess'], 3)} | "
              f"{pct(v['model_top10'])} | {pct(v['reference_top10'])} | {v['wins']}/{v['months']} | "
              f"{pct(v['mean_diff'], 3)} ± {pct(v['se'], 3)} | {'**Başarılı**' if v['success'] else 'Başarısız'} |")
    print("\nAylık MAE farkı: LightGBM eksi referans (negatif: LightGBM daha iyi).\n")

    print("## 5. Ay ay: fazla getiri MAE'si ve ilk 10\n")
    names = ["lightgbm", "drift", "momentum", "sifir"]
    by_month = {}
    for r in rep["monthly"]:
        by_month.setdefault(r["date"], {})[r["model"]] = r
    print("| Ay | " + " | ".join(f"MAE {n}" for n in names) + " | " + " | ".join(f"İlk 10 {n}" for n in names[:3])
          + " | Tüm fonlar | PP medyanı |\n|---|" + "---|" * (len(names) + 3 + 2))
    for d, ms in sorted(by_month.items()):
        any_ = next(iter(ms.values()))
        print(f"| {d[5:7]}.{d[:4]} | " + " | ".join(pct(ms.get(n, {}).get("mae_excess")) for n in names) + " | "
              + " | ".join(pct(ms.get(n, {}).get("top10")) for n in names[:3]) + f" | {pct(any_['universe'])} | {pct(any_['mm'])} |")
    print()

    print("## 6. Özellik önemi (son test ayında eğitilen LightGBM, kazanç payı)\n")
    print("| Özellik | Pay |\n|---|---|")
    for r in rep["importance"]:
        print(f"| {r['feature']} | {pct(r['share'], 1)} |")
    print()

    print("## 7. Sitede gösterilen tahmin: drift ve konformal %80 aralık (ham getiri)\n")
    print("| Risk grubu | Hata %10 dilimi | Hata %90 dilimi | Hata sayısı | Test dönemi kapsamı |\n|---|---|---|---|---|")
    for g, v in rep["drift_interval"].items():
        n = f"{v['n']:,}".replace(",", ".")
        print(f"| {GROUP_LABELS[g]} | {pct(v['q10'])} | {pct(v['q90'])} | {n} | {pct(v['coverage'], 1)} |")
    print()

    if rep.get("arima"):
        a = rep["arima"]
        print(f"## 8. ARIMA ({a['funds']} fonluk tabakalı örnek)\n")
        print("Aynı fonlar ve test aylarında karşılaştırma (ilk 10 bu küçük örnekte anlamlı olmadığından gösterilmez):\n")
        table(a["rows"])
        print("Seçilen mertebeler: " + ", ".join(f"{k} {v} fon" for k, v in a["orders"].items()) + "\n")

    if rep.get("exploration"):
        x = rep["exploration"]
        print("## 9. KEŞİF VARYANTI (test sonuçları görüldükten sonra tanımlandı)\n")
        print("Hedef: fonun aynı ay içindeki fazla getiri yüzdelik sırası. Ay içinde bütün fonlar için aynı olan özellikler "
              "(mm_ret_1m, mm_ret_12m) çıkarıldı. Hiperparametreler asıl modelinkiyle aynı, yeniden ayar yapılmadı. "
              "Sıra tahmini MAE için son eğitim ayının fazla getiri dağılımına çevrildi; asıl ölçüt sıralama korelasyonu ve ilk 10. "
              "Bu bölüm sitedeki kararı değiştirmez.\n")
        table(x["overall"])
        for g, rows in x["groups"].items():
            print(f"**{GROUP_LABELS[g]}**\n")
            table(rows)
        print("Özellik önemi: " + ", ".join(f"{r['feature']} {pct(r['share'], 1)}" for r in x["importance"][:6]) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arima", action="store_true", help="ARIMA'yı 40 fonluk örnekte de değerlendir (~4 dk)")
    ap.add_argument("--ayar", action="store_true", help="Hiperparametre ayarını yeniden yap (sadece ayar dönemi)")
    ap.add_argument("--kesifsiz", action="store_true", help="Keşif varyantını atla")
    ap.add_argument("--kaydet", action="store_true", help="Sonucu ml_reports tablosuna da yaz (model performansı sayfası)")
    ap.add_argument("--kayittan", action="store_true", help="Hesaplamadan, ml_reports'taki son raporu markdown'a çevir")
    args = ap.parse_args()
    t0 = time.time()
    if args.kayittan:
        from app.ml.job import latest_report

        with SessionLocal() as db:
            last = latest_report(db)
        if last is None:
            sys.exit("ml_reports boş; önce --kaydet ile çalıştır.")
        render(last.payload)
        return
    with SessionLocal() as db:
        panel = load_panel(db)
        data = build_dataset(panel, month_starts(panel))
        log(f"Veri: {len(data):,} satır, {time.time() - t0:.0f} sn")
        rep = build_report(panel, data, do_tune=args.ayar, arima=args.arima, explore=not args.kesifsiz,
                           log=lambda m: log(f"{m} ({time.time() - t0:.0f} sn)"))
        if args.kaydet:
            from app.ml.job import save_report

            init_db()
            save_report(db, rep)
            log("ml_reports tablosuna yazıldı")
    render(rep)
    log(f"Toplam: {time.time() - t0:.0f} sn")


if __name__ == "__main__":
    main()
