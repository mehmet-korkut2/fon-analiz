"""Öneri sistemi analizleri (rapor için, veritabanını değiştirmez). Çıktı markdown'dır.

    python -m scripts.oneri_analizi > ../docs/oneri_analizi_cikti.md

1. RA modu: düşük volatiliteli fonların "riske göre getiri" puanı ayrı havuzda mı, tüm havuzda mı
   hesaplanmalı? Dengeli profilin ilk 10'u iki modda karşılaştırılır.
2. Ağırlık duyarlılığı: her profilde ağırlıklar değiştirildiğinde ilk 10 ne kadar değişiyor?
3. Kayan pencereli geriye dönük test (backtest_windows tablosundan).
4. Örnek kişiler: anket -> profil -> öneri -> örnek portföy.
5. Dengeli profilde riskli fon kotasının etkisi (öneriler ve kayan pencere).
"""
import pandas as pd

from app.database import SessionLocal
from app.services import recommender as R
from app.services import risk_survey as rs

PROFILES = ("temkinli", "dengeli", "agresif")


def pct(v) -> str:
    """-0.053 -> '-%5,3'"""
    if v is None or pd.isna(v):
        return "–"
    return ("-" if v < -0.0005 else "") + f"%{abs(v) * 100:.1f}".replace(".", ",")


def num(v, d=2) -> str:
    return "–" if v is None or pd.isna(v) else f"{v:.{d}f}".replace(".", ",")


def top10(df, profile, rf, **kw) -> pd.DataFrame:
    return R.diversify(R.score(R.eligible(df, profile, False), profile, rf, **kw), 10)


def ra_mode_section(df, rf):
    print("## 1. RA modu: dengeli profilin ilk 10'u\n")
    tum = top10(df, "dengeli", rf, ra_mode="tum")
    ayri = top10(df, "dengeli", rf, ra_mode="ayri")
    pool = R.score(R.eligible(df, "dengeli", False), "dengeli", rf)
    print(f"Dengeli havuz: {len(pool)} fon; bunların {int(pool['low_vol'].sum())}'i düşük volatiliteli (%5 altı, Sharpe yok).\n")
    print("| Sıra | Tüm havuz (seçilen) | puan | vol | Ayrı havuz | puan | vol |")
    print("|---|---|---|---|---|---|---|")
    for i in range(10):
        a = tum.iloc[i] if i < len(tum) else None
        b = ayri.iloc[i] if i < len(ayri) else None
        cell = lambda r: (f"{r['code']} ({r['category']})", num(r["score"], 3), pct(r["vol"])) if r is not None else ("", "", "")  # noqa: E731
        print(f"| {i + 1} | " + " | ".join(cell(a)) + " | " + " | ".join(cell(b)) + " |")
    common = set(tum["code"]) & set(ayri["code"])
    print(f"\nOrtak fon: {len(common)}/10. Sadece tüm havuzda: {', '.join(sorted(set(tum['code']) - common)) or '–'}. "
          f"Sadece ayrı havuzda: {', '.join(sorted(set(ayri['code']) - common)) or '–'}.")
    for name, t in (("Tüm havuz", tum), ("Ayrı havuz", ayri)):
        print(f"- {name}: ilk 10'da düşük volatiliteli fon {int(t['low_vol'].sum())}, medyan volatilite {pct(t['vol'].median())}, "
              f"medyan 1 yıllık getiri {pct(t['ret_1y'].median())}, medyan maks. düşüş {pct(t['mdd'].median())}")
    print()


def variants(base: dict) -> dict[str, dict]:
    out = {"Temel": base, "Eşit ağırlık": {c: 0.25 for c in R.COMPONENTS}}
    for c in R.COMPONENTS:
        w = {k: (v * 0.9 if k != c else v * 0.9 + 0.10) for k, v in base.items()}  # c'ye +0,10, diğerleri orantılı azalır
        out[f"{R.COMPONENT_LABELS[c]} +0,10"] = w
    for c in R.COMPONENTS:
        rest = sum(v for k, v in base.items() if k != c)
        out[f"{R.COMPONENT_LABELS[c]} yok"] = {k: (0 if k == c else v / rest) for k, v in base.items()}
    return out


def sensitivity_section(df, rf):
    print("## 2. Ağırlık duyarlılığı\n")
    print("Her satırda ağırlıklar değiştirilip ilk 10 (kategori sınırıyla) yeniden seçildi. **Ortak**: temel ilk 10 ile "
          "kaç fonun aynı kaldığı. **Spearman**: havuzdaki tüm fonların puan sıralamasının temel sıralamayla korelasyonu.\n")
    for profile in PROFILES:
        pool = R.eligible(df, profile, False)
        base_w = R.WEIGHTS[profile]
        base_scored = R.score(pool, profile, rf)
        base_top = set(R.diversify(base_scored, 10)["code"])
        print(f"### {profile.capitalize()} (havuz {len(pool)} fon)\n")
        print("| Ağırlıklar (G / RA / D / T) | Ortak | Spearman | Yeni girenler |")
        print("|---|---|---|---|")
        for name, w in variants(base_w).items():
            s = R.score(pool, profile, rf, weights=w)
            top = set(R.diversify(s, 10)["code"])
            # Spearman = sıralamaların Pearson korelasyonu (scipy gerektirmesin)
            a, b = base_scored.set_index("code")["score"].align(s.set_index("code")["score"])
            rho = a.rank().corr(b.rank())
            ws = " / ".join(num(w[c]) for c in R.COMPONENTS)
            print(f"| {name}: {ws} | {len(top & base_top)}/10 | {num(rho)} | {', '.join(sorted(top - base_top)) or '–'} |")
        print()


PERSONAS = {
    "Ayşe, 26, uzun vadeli birikim": dict(vade=4, kayip=3, davranis=3, hedef=3, gelir=3, birikim=2, birikim_payi=3, deneyim=2),
    "Mehmet, 58, emekliliğe 2 yıl": dict(vade=1, kayip=1, davranis=1, hedef=1, gelir=3, birikim=4, birikim_payi=2, deneyim=1),
    "Zeynep, 40, orta yol": dict(vade=3, kayip=2, davranis=2, hedef=2, gelir=3, birikim=3, birikim_payi=2, deneyim=2),
    "Can, 30, birikimi yok ama riskli": dict(vade=4, kayip=4, davranis=4, hedef=4, gelir=2, birikim=0, birikim_payi=1, deneyim=3),
}


def persona_section(db):
    print("## 4. Örnek kişiler\n")
    for name, answers in PERSONAS.items():
        r = rs.evaluate(answers)
        caps = "; ".join(c.message for c in r.caps) or "yok"
        rec = R.recommend(db, r.profile, False, 5)
        roll = R.summarize_windows(R.load_windows(db, r.profile, False))
        print(f"### {name}\n")
        print(f"- Puan {r.score}/100 → puana göre {r.score_profile}, sonuç **{r.profile}** (sınır: {caps})")
        print(f"- İlk 5 öneri: " + ", ".join(f"{x.code} ({x.category}, risk {int(x.risk_level)})" for x in rec.items.itertuples()))
        print(f"- Örnek portföy: {', '.join(rec.portfolio['code'])}")
        if roll:
            print(f"- Kayan pencereli test ({r.profile}): {roll['beats']}/{roll['windows']} dönemde para piyasası medyanını geçti, "
                  f"ortalama fazla getiri {signed(roll['mean_excess'])}")
        print()


def signed(v) -> str:
    return ("+" if v >= 0 else "") + pct(v)


def backtest_section(db):
    print("## 3. Kayan pencereli geriye dönük test\n")
    print(f"Son {R.ROLLING_YEARS} yılda her ayın ilk işlem günü o güne kadarki veriyle seçim, {R.BACKTEST_MONTHS} ay tutma; "
          "kıyas para piyasası fonlarının medyanı. Kaynak: backtest_windows tablosu (`python -m scripts.geriye_donuk_test`).\n")
    for qualified in (False, True):
        print(f"**{'Nitelikli yatırımcı (serbest fonlar dahil)' if qualified else 'Nitelikli olmayan yatırımcı'}**\n")
        print("| Profil | Dönem | PP medyanını geçtiği | Ort. fazla getiri | Medyan fazla getiri | Ort. portföy / PP | En iyi dönem | En kötü dönem |")
        print("|---|---|---|---|---|---|---|---|")
        for profile in PROFILES:
            s = R.summarize_windows(R.load_windows(db, profile, qualified))
            if not s:
                print(f"| {profile} | 0 | – | – | – | – | – | – |")
                continue
            b, w = s["best"], s["worst"]
            print(f"| {profile} | {s['windows']} | {s['beats']}/{s['windows']} | {signed(s['mean_excess'])} | {signed(s['median_excess'])} | "
                  f"{pct(s['mean_portfolio'])} / {pct(s['mean_benchmark'])} | {b.start:%m.%Y}: {signed(b.excess)} | {w.start:%m.%Y}: {signed(w.excess)} |")
        print()


def quota_section(db, df, rf):
    print("## 5. Dengeli profil: riskli fon kotası\n")
    print(f"Kota: önerilerin ve örnek portföyün en az {R.RISKY_QUOTA['dengeli']}'si risk değeri {R.RISKY_MIN_LEVEL}+ ve volatilitesi %5+ fonlardan.\n")
    saved = dict(R.RISKY_QUOTA)
    rows = []
    try:
        for label, quota in (("Kotalı (kullanılan)", saved), ("Kotasız", {})):
            R.RISKY_QUOTA = quota
            rec = R.recommend_from(df, None, "dengeli", False, rf=rf)
            s = R.summarize_windows(R.rolling_backtest(db, profiles=("dengeli",), qualified_options=(False,)))
            rows.append((label, rec, s))
    finally:
        R.RISKY_QUOTA = saved
    print("| | İlk 10 | Örnek portföy | PP medyanını geçtiği | Ort. fazla getiri | Medyan fazla getiri |")
    print("|---|---|---|---|---|---|")
    for label, rec, s in rows:
        print(f"| {label} | {', '.join(rec.items['code'])} | {', '.join(rec.portfolio['code'])} | {s['beats']}/{s['windows']} | "
              f"{signed(s['mean_excess'])} | {signed(s['median_excess'])} |")
    print()


def main():
    with SessionLocal() as db:
        df, latest = R.current_candidates(db)
        rf = R.risk_free_from(df)
        print(f"# Öneri sistemi analizleri\n\nVeri tarihi: {latest}. Aday havuzu: {len(df)} fon. Risksiz getiri: {pct(rf)}.\n")
        ra_mode_section(df, rf)
        sensitivity_section(df, rf)
        backtest_section(db)
        persona_section(db)
        quota_section(db, df, rf)


if __name__ == "__main__":
    main()
