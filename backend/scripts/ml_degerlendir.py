"""ML tahmin modülünün walk-forward değerlendirmesi (veritabanını değiştirmez). Çıktı markdown'dır.

    python -m scripts.ml_degerlendir > ../docs/ml_tahmin_cikti.md           # ~5-10 dk
    python -m scripts.ml_degerlendir --arima > ../docs/ml_tahmin_cikti.md   # + ARIMA (40 fon), +5-15 dk
    python -m scripts.ml_degerlendir --ayarsiz                               # hiperparametre ayarı yok

Takvim (sonuçlar görülmeden önce belirlendi):
- Ayar dönemi: 10.2023 - 09.2024 aybaşları. LightGBM hiperparametreleri sadece burada seçilir.
- Test dönemi: 10.2024 - 09.2026 aybaşları (24 ay). Ayar sırasında hiç kullanılmaz.
Her ay model, hedef penceresi o aybaşından önce biten örneklerle yeniden eğitilir.

Başarı ölçütü (risk grubu bazında): model, o grubun en iyi referansına (test döneminde fazla getiri
MAE'si en düşük referans) göre hem daha düşük fazla getiri MAE'si hem de daha yüksek "ilk 10"
getirisi sağlarsa başarılı sayılır.
"""
import argparse
import itertools
import sys
import time

import numpy as np
import pandas as pd

from app.database import SessionLocal
from app.ml import evaluation as E
from app.ml.features import HORIZON, RISK_GROUPS, build_dataset, load_panel, month_starts
from app.ml.models import BASELINES, LGBM_DEFAULTS, Arima, LightGBM, select_arima_order

VALID = (pd.Timestamp("2023-10-01"), pd.Timestamp("2024-09-30"))
TEST = (pd.Timestamp("2024-10-01"), pd.Timestamp("2026-09-30"))
GRID = {"num_leaves": [7, 15, 31], "min_child_samples": [100, 400], "n_estimators": [150, 400]}
ARIMA_PER_GROUP = 10
SEED = 42

GROUP_LABELS = {"1-2": "Risk 1-2", "3-4": "Risk 3-4", "5-7": "Risk 5-7", "bilinmiyor": "Risk değeri yok"}
COLS = [("n", "Örnek"), ("mae", "MAE"), ("rmse", "RMSE"), ("mae_excess", "Fazla MAE"), ("rmse_excess", "Fazla RMSE"),
        ("dir_raw", "Ham yön"), ("dir_excess", "PP üstü/altı yönü"), ("ic", "Sıralama korel."), ("top10", "İlk 10 (aylık)"),
        ("coverage", "%80 aralık kapsamı")]


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def pct(v, d=2):
    return "–" if v is None or pd.isna(v) else ("-" if v < 0 else "") + f"%{abs(v) * 100:.{d}f}".replace(".", ",")


def num(v, d=3):
    return "–" if v is None or pd.isna(v) else f"{v:.{d}f}".replace(".", ",")


def fmt(col, v, model=None):
    if col == "n":
        return f"{int(v):,}".replace(",", ".")
    if col == "ic":
        return num(v)
    if col == "dir_raw" and model == "sifir":
        return "–"  # sıfır tahmini yön söylemez
    return pct(v, 1 if col in ("dir_raw", "dir_excess", "coverage") else 2)


def table(df, first_col, first_label, label_map=None):
    cols = [c for c in COLS if c[0] in df.columns]
    print(f"| {first_label} | " + " | ".join(lbl for _, lbl in cols) + " |")
    print("|---|" + "---|" * len(cols))
    for _, r in df.iterrows():
        name = label_map.get(r[first_col], r[first_col]) if label_map else r[first_col]
        print(f"| {name} | " + " | ".join(fmt(c, r[c], r.get("model")) for c, _ in cols) + " |")
    print()


def tune(data, origins):
    log(f"Ayar: {len(list(itertools.product(*GRID.values())))} aday x {len(origins)} ay")
    results = []
    for values in itertools.product(*GRID.values()):
        params = dict(zip(GRID, values))
        p = E.walk_forward(data, origins, LightGBM(**params))
        results.append({**params, "mae_excess": E.monthly(p)["mae_excess"].mean()})
    res = pd.DataFrame(results).sort_values("mae_excess")
    best = {k: (int(v) if isinstance(v, (np.integer, float)) and float(v).is_integer() else v) for k, v in res.iloc[0][list(GRID)].items()}
    return best, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arima", action="store_true", help="ARIMA'yı 40 fonluk örnekte de değerlendir")
    ap.add_argument("--ayarsiz", action="store_true", help="Hiperparametre ayarı yapmadan varsayılanlarla")
    args = ap.parse_args()
    t0 = time.time()

    with SessionLocal() as db:
        panel = load_panel(db)
    origins = month_starts(panel)
    data = build_dataset(panel, origins)
    valid = [t for t in origins if VALID[0] <= t <= VALID[1]]
    test = [t for t in origins if TEST[0] <= t <= TEST[1]]
    log(f"Veri: {len(data):,} satır, {time.time() - t0:.0f} sn")

    print("# ML tahmin modülü: walk-forward değerlendirme çıktısı\n")
    print(f"Veri: {len(origins)} aybaşı ({origins[0]:%d.%m.%Y} – {origins[-1]:%d.%m.%Y}), {len(data):,} örnek, "
          f"{data['code'].nunique()} fon. Hedef: {HORIZON} işlem günlük getiri.  ")
    print(f"Ayar dönemi: {len(valid)} ay ({valid[0]:%m.%Y} – {valid[-1]:%m.%Y}). Test dönemi: {len(test)} ay "
          f"({test[0]:%m.%Y} – {test[-1]:%m.%Y}), {int((data['date'].isin(test)).sum()):,} tahmin.\n")

    # 1. Ayar
    print("## 1. LightGBM hiperparametre ayarı (sadece ayar dönemi)\n")
    if args.ayarsiz:
        best = {k: LGBM_DEFAULTS[k] for k in GRID}
        print(f"Ayar yapılmadı (--ayarsiz); varsayılanlar: {best}\n")
    else:
        best, res = tune(data, valid)
        print("Seçim ölçütü: ayar dönemindeki aylık fazla getiri MAE'sinin ortalaması. En iyi 5 aday:\n")
        print("| num_leaves | min_child_samples | n_estimators | Fazla MAE |\n|---|---|---|---|")
        for _, r in res.head(5).iterrows():
            print(f"| {int(r.num_leaves)} | {int(r.min_child_samples)} | {int(r.n_estimators)} | {pct(r.mae_excess, 3)} |")
        print(f"\nSeçilen: {best}. Diğer parametreler: objective=l1, learning_rate=0,03, subsample=0,8, colsample=0,8.\n")
    log(f"Ayar bitti: {time.time() - t0:.0f} sn")

    # 2. Test dönemi tahminleri
    lgbm = LightGBM(**best)
    hist = E.walk_forward(data, valid, LightGBM(**best))  # aralık için ayar dönemindeki hatalar
    preds = [E.walk_forward(data, test, m) for m in BASELINES]
    preds.append(E.walk_forward(data, test, lgbm))
    base_hist = {m.name: E.walk_forward(data, valid, m) for m in BASELINES}
    preds = [E.add_intervals(p, pd.concat([hist if p["model"].iloc[0] == "lightgbm" else base_hist[p["model"].iloc[0]]]))
             for p in preds]
    P = pd.concat(preds, ignore_index=True)
    log(f"Test tahminleri bitti: {time.time() - t0:.0f} sn")
    labels = {m.name: m.label for m in [*BASELINES, lgbm]}

    print("## 2. Test dönemi: genel sonuçlar\n")
    print("MAE/RMSE ham getiri, \"Fazla\" PP medyanına göre fazla getiri üzerinden. Ham yön: getirinin işareti "
          "(getirilerin çoğu pozitif olduğundan yanıltıcı). PP üstü/altı yönü: fonun PP medyanını geçip geçmeyeceği. "
          "Sıralama korel.: ay içinde tahmin ve gerçekleşen fazla getirinin Spearman korelasyonu (ortalama). "
          "İlk 10: her ay tahmini en yüksek 10 fonun gerçekleşen ortalama getirisi.\n")
    overall = E.summarize(P, by_group=False).sort_values("mae_excess")
    table(overall, "model", "Model", labels)
    m = E.monthly(P)
    uni = m.groupby("date")[["universe", "mm"]].first().mean()
    print(f"Kıyas: aynı aylarda tüm fonların ortalama getirisi {pct(uni['universe'])}, PP medyanı {pct(uni['mm'])}.\n")

    print("## 3. Risk grubuna göre\n")
    by = E.summarize(P, by_group=True)
    verdicts = []
    for g in RISK_GROUPS:
        sub = by[by["risk_group"] == g].sort_values("mae_excess")
        if sub.empty:
            continue
        print(f"### {GROUP_LABELS[g]} ({int(sub['n'].iloc[0]):,} tahmin)\n".replace(",", "."))
        table(sub, "model", "Model", labels)
        refs = sub[sub["model"] != "lightgbm"]
        best_ref = refs.iloc[0]
        lg = sub[sub["model"] == "lightgbm"].iloc[0]
        ok_mae = lg["mae_excess"] < best_ref["mae_excess"]
        ok_top = lg["top10"] > best_ref["top10"] if not pd.isna(best_ref["top10"]) else True
        h = E.head_to_head(P, "lightgbm", best_ref["model"], group=g)
        verdicts.append((g, best_ref["model"], lg, best_ref, ok_mae, ok_top, h))

    print("## 4. Başarı ölçütü (risk grubu bazında)\n")
    print("| Risk grubu | En iyi referans | LightGBM fazla MAE | Referans fazla MAE | LightGBM ilk 10 | Referans ilk 10 | "
          "LightGBM'in daha iyi olduğu ay | Aylık MAE farkı (± std. hata) | Sonuç |")
    print("|---|---|---|---|---|---|---|---|---|")
    for g, ref, lg, br, ok_mae, ok_top, h in verdicts:
        res = "**Başarılı**" if ok_mae and ok_top else "Başarısız"
        print(f"| {GROUP_LABELS[g]} | {labels[ref]} | {pct(lg['mae_excess'], 3)} | {pct(br['mae_excess'], 3)} | {pct(lg['top10'])} | "
              f"{pct(br['top10'])} | {h['wins']}/{h['months']} | {pct(h['mean_diff'], 3)} ± {pct(h['se'], 3)} | {res} |")
    print("\nAylık MAE farkı: LightGBM eksi referans (negatif: LightGBM daha iyi).\n")

    print("## 5. Ay ay: fazla getiri MAE'si ve ilk 10\n")
    piv = m.pivot(index="date", columns="model", values="mae_excess")
    top = m.pivot(index="date", columns="model", values="top10")
    names = [c for c in ["lightgbm", "drift", "momentum", "sifir"] if c in piv]
    print("| Ay | " + " | ".join(f"MAE {n}" for n in names) + " | " + " | ".join(f"İlk 10 {n}" for n in names if n != "sifir")
          + " | Tüm fonlar | PP medyanı |")
    print("|---|" + "---|" * (2 * len(names) - 1 + 2))
    uni_m = m.groupby("date")[["universe", "mm"]].first()
    for t in piv.index:
        print(f"| {t:%m.%Y} | " + " | ".join(pct(piv.at[t, n]) for n in names) + " | "
              + " | ".join(pct(top.at[t, n]) for n in names if n != "sifir")
              + f" | {pct(uni_m.at[t, 'universe'])} | {pct(uni_m.at[t, 'mm'])} |")
    print()

    print("## 6. Özellik önemi (son test ayında eğitilen model, kazanç payı)\n")
    final = LightGBM(**best).fit(E.train_rows(data, test[-1]))
    print("| Özellik | Pay |\n|---|---|")
    for f, v in final.importance().items():
        print(f"| {f} | {pct(v, 1)} |")
    print()

    if args.arima:
        print("## 7. ARIMA (40 fonluk tabakalı örnek)\n")
        t_first = test[0]
        eligible = data[data["date"].isin(test)].groupby("code")["date"].nunique()
        full = set(eligible.index[eligible == len(test)])
        first = data[(data["date"] == t_first) & data["code"].isin(full)]
        rng = np.random.default_rng(SEED)
        sample = []
        for g in RISK_GROUPS:
            codes = sorted(first.loc[first["risk_group"] == g, "code"])
            sample += list(rng.choice(codes, size=min(ARIMA_PER_GROUP, len(codes)), replace=False))
        log(f"ARIMA: {len(sample)} fon için mertebe seçimi")
        # mertebe: ilk test ayından önceki son gün itibarıyla (test verisi görülmeden)
        pre = panel.prices.index[panel.prices.index < t_first][-1]
        orders = {c: select_arima_order(panel, c, pre) for c in sample}
        sub = data[data["code"].isin(sample)]
        ar = E.walk_forward(sub, test, Arima(panel, orders, HORIZON))
        log(f"ARIMA bitti: {time.time() - t0:.0f} sn")
        same = P[P["code"].isin(sample)]
        cmp_ = E.summarize(pd.concat([same, ar]), by_group=False).sort_values("mae_excess")
        print(f"Aynı {len(sample)} fon ve {len(test)} test ayında karşılaştırma (ilk 10 bu küçük örnekte anlamlı olmadığından gösterilmez):\n")
        table(cmp_.drop(columns=["top10", "coverage"], errors="ignore"), "model", "Model", {**labels, "arima": "ARIMA (fon bazında)"})
        oc = pd.Series([f"({p},0,{q})" for p, _, q in orders.values()]).value_counts()
        print("Seçilen mertebeler: " + ", ".join(f"{k} {v} fon" for k, v in oc.items()) + "\n")

    log(f"Toplam: {time.time() - t0:.0f} sn")


if __name__ == "__main__":
    main()
