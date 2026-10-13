"""Öneri sistemi analizleri (rapor için, veritabanını değiştirmez). Çıktı markdown'dır.

    python -m scripts.oneri_analizi > ../docs/oneri_analizi_cikti.md

1. RA modu: düşük volatiliteli fonların "riske göre getiri" puanı ayrı havuzda mı, tüm havuzda mı
   hesaplanmalı? Dengeli profilin ilk 10'u iki modda karşılaştırılır.
2. Ağırlık duyarlılığı: her profilde ağırlıklar değiştirildiğinde ilk 10 ne kadar değişiyor?
3. Örnek kişiler: anket -> profil -> öneri -> örnek portföy -> geriye dönük test.
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
    "Ayşe, 26, uzun vadeli birikim": dict(vade=4, kayip=3, davranis=3, hedef=3, gelir=3, birikim=2, deneyim=2),
    "Mehmet, 58, emekliliğe 2 yıl": dict(vade=1, kayip=1, davranis=1, hedef=1, gelir=3, birikim=4, deneyim=1),
    "Zeynep, 40, orta yol": dict(vade=3, kayip=2, davranis=2, hedef=2, gelir=3, birikim=3, deneyim=2),
    "Can, 30, birikimi yok ama riskli": dict(vade=4, kayip=4, davranis=4, hedef=4, gelir=2, birikim=0, deneyim=3),
}


def persona_section(db):
    print("## 4. Örnek kişiler\n")
    for name, answers in PERSONAS.items():
        r = rs.evaluate(answers)
        caps = "; ".join(c.message for c in r.caps) or "yok"
        rec = R.recommend(db, r.profile, False, 5)
        bt = R.backtest(db, r.profile, False)
        p = bt.performance if bt else None
        print(f"### {name}\n")
        print(f"- Puan {r.score}/100 → puana göre {r.score_profile}, sonuç **{r.profile}** (sınır: {caps})")
        print(f"- İlk 5 öneri: " + ", ".join(f"{x.code} ({x.category}, risk {int(x.risk_level)})" for x in rec.items.itertuples()))
        print(f"- Örnek portföy: {', '.join(rec.portfolio['code'])}")
        if p:
            print(f"- Geriye dönük test ({bt.selection_date} seçim → {p.end}): portföy {pct(p.portfolio['return'])}, "
                  f"para piyasası medyanı {pct(p.benchmark['return'])}; portföy volatilitesi {pct(p.portfolio['volatility'])}, "
                  f"maks. düşüş {pct(p.portfolio['max_drawdown'])}. Seçilen fonlar: "
                  + ", ".join(f"{k} {pct(v)}" for k, v in p.funds.items()))
        print()


def backtest_section(db):
    print("## 3. Geriye dönük test özeti\n")
    print("| Profil | Seçim günü | Seçimdeki risksiz getiri | Portföy | Getiri | Kıyas (PP medyanı) | Fark | Volatilite | Maks. düşüş |")
    print("|---|---|---|---|---|---|---|---|---|")
    for profile in PROFILES:
        bt = R.backtest(db, profile, False)
        p = bt.performance
        if not p:
            print(f"| {profile} | {bt.selection_date} | – | – | – | – | – | – | – |")
            continue
        diff = p.portfolio["return"] - p.benchmark["return"]
        print(f"| {profile} | {bt.selection_date} | {pct(bt.recommendation.risk_free_rate)} | {', '.join(bt.recommendation.portfolio['code'])} | "
              f"{pct(p.portfolio['return'])} | {pct(p.benchmark['return'])} | {'+' if diff >= 0 else ''}{pct(diff)} | "
              f"{pct(p.portfolio['volatility'])} | {pct(p.portfolio['max_drawdown'])} |")
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


if __name__ == "__main__":
    main()
