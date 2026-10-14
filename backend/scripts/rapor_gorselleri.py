"""Rapor görsellerini veritabanından üretir: docs/rapor/gorseller/*.png (veritabanını değiştirmez).

    python -m scripts.rapor_gorselleri

Arayüz ekran görüntüleri (sekil_4_*) bu betikle değil, uygulama çalışırken tarayıcıdan alınır.
Renkler sitedekiyle aynı (renk körlüğü kontrolünden geçmiş kategorik palet).
"""
from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from app.config import settings  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "rapor" / "gorseller"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
GREEN, RED, INK, MUTED, GRID = "#0f7a5c", "#b3261e", "#17211d", "#5d6b65", "#e5ebe8"

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 200, "font.family": "DejaVu Sans", "font.size": 9,
    "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.axisbelow": True, "axes.titlesize": 10, "axes.titleweight": "bold",
    "legend.frameon": False,
})


def pct_axis(ax, axis="y", decimals=0):
    """-0.2 -> '-%20'"""
    fmt = matplotlib.ticker.FuncFormatter(
        lambda v, _: ("-" if v < -1e-12 else "") + f"%{abs(v) * 100:.{decimals}f}".replace(".", ","))
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def date_axis(ax, fmt="%m.%Y", months=None):
    """Kısa tarih etiketleri (üst üste binmesin)."""
    import matplotlib.dates as mdates

    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=months) if months else mdates.AutoDateLocator(maxticks=8))
    ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("yazıldı:", name)


def db_path() -> str:
    url = settings.database_url
    assert url.startswith("sqlite:///"), "Bu betik yerel SQLite veritabanı için"
    return str((Path(__file__).resolve().parents[1] / url.removeprefix("sqlite:///")).resolve())


# --- 1. Mimari -------------------------------------------------------------------------

def mimari():
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    def box(x, y, w, h, title, lines, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.5", fc="white", ec=color, lw=1.4))
        ax.text(x + w / 2, y + h - 3.2, title, ha="center", va="top", fontsize=9, fontweight="bold", color=INK)
        ax.text(x + w / 2, y + h - 8, "\n".join(lines), ha="center", va="top", fontsize=7.2, color=MUTED, linespacing=1.4)

    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1))
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 1.2, label, ha="center", fontsize=6.8, color=MUTED)

    box(1, 40, 22, 18, "Dış kaynaklar", ["TEFAS JSON API", "TCMB today.xml", "Truncgil (anlık döviz)", "SPK bülteni (elle)"], ORANGE)
    box(30, 4, 40, 54, "Backend (FastAPI, Python)", [
        "updater: fon listesi + fiyatlar", "scheduler: hafta içi 21:00, açılışta tamamlama",
        "metrics_job: getiri, volatilite, Sharpe, maks. düşüş", "fund_status / data_quality",
        "recommender: öneri, örnek portföy,", "kayan pencereli geriye dönük test",
        "ml: walk-forward değerlendirme, tahmin", "", "routers: funds, compare, rankings, risk,",
        "recommendations, ml, fx, status"], BLUE)
    box(77, 34, 22, 24, "Frontend", ["React 19 + Vite", "React Router, axios", "Recharts", "Profil: localStorage"], AQUA)
    box(1, 4, 22, 26, "Veritabanı (SQLite)", ["funds, prices", "fund_metrics", "backtest_windows", "forecasts, ml_reports", "users, risk_profiles"], GREEN)
    arrow(23, 49, 30, 49, "HTTP")
    arrow(30, 17, 23, 17, "SQLAlchemy")
    arrow(70, 46, 77, 46, "JSON API")
    save(fig, "sekil_1_1_mimari.png")


# --- 2. Veri toplama ---------------------------------------------------------------------

def fon_sayisi(prices):
    m = prices.assign(ay=prices["date"].dt.to_period("M")).groupby("ay")["code"].nunique()
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.plot(m.index.to_timestamp(), m.values, color=BLUE, lw=2)
    date_axis(ax, "%Y", months=12)
    ax.set_ylabel("Fiyatı olan fon sayısı")
    ax.set_title("Aylara göre fiyat verisi olan fon sayısı (TEFAS, yatırım fonları)")
    ax.set_ylim(0, m.max() * 1.1)
    save(fig, "sekil_2_1_fon_sayisi.png")


def spk_fonlari(prices):
    codes = {"KHA": "KHA (Pardus, hisse)", "AC4": "AC4 (Pardus, para piyasası)", "TLY": "TLY (Tera, serbest)"}
    sub = prices[prices["code"].isin(codes) & (prices["date"] >= "2026-07-01")]
    fig, ax = plt.subplots(figsize=(7, 3))
    for (code, label), color in zip(codes.items(), [BLUE, ORANGE, AQUA]):
        s = sub[sub["code"] == code].set_index("date")["price"]
        ax.plot(s.index, s / s.iloc[0] * 100, color=color, lw=2, label=label)
    ax.set_yscale("log")
    ax.set_yticks([0.01, 0.1, 1, 10, 100], ["0,01", "0,1", "1", "10", "100"])
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.axvline(pd.Timestamp("2026-09-17"), color=MUTED, ls="--", lw=1)
    ax.text(pd.Timestamp("2026-09-14"), 20, "SPK Bülteni 2026/60\n(17.09.2026)", fontsize=7, color=MUTED, va="top", ha="right")
    date_axis(ax, "%d.%m.%Y", months=1)
    ax.set_ylabel("Fiyat (01.07.2026 = 100, log)")
    ax.set_title("SPK kararıyla işleme kapatılan şirketlerin fonlarından örnekler")
    ax.legend(loc="lower left", fontsize=7.5)
    save(fig, "sekil_2_2_spk_fonlari.png")


# --- 3. Metrikler ------------------------------------------------------------------------

def pazartesi(prices):
    days = ["Pzt", "Sal", "Çar", "Per", "Cum"]
    fig, ax = plt.subplots(figsize=(6, 2.8))
    width = 0.38
    for i, (code, label, color) in enumerate([("PRU", "PRU (kısa vadeli serbest)", BLUE), ("TTE", "TTE (hisse senedi)", ORANGE)]):
        s = prices[prices["code"] == code].set_index("date")["price"].sort_index()
        s = s.loc[s.index[-1] - pd.DateOffset(years=1):]
        r = s.pct_change().dropna()
        by = r.groupby(r.index.dayofweek).mean().reindex(range(5))
        ax.bar(np.arange(5) + (i - 0.5) * width, by.values, width, color=color, label=label)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xticks(range(5), days)
    pct_axis(ax, decimals=1)
    ax.set_ylabel("Ortalama günlük getiri")
    ax.set_title("Haftanın gününe göre ortalama getiri (son 1 yıl)")
    ax.legend(fontsize=7.5)
    save(fig, "sekil_3_1_pazartesi.png")


def sharpe_vol(con):
    m = pd.read_sql("""select m.volatility_1y vol, m.ret_1y, f.category from fund_metrics m join funds f on f.code=m.fund_code
                       where m.volatility_1y is not null and m.ret_1y is not null and coalesce(f.status,'aktif')='aktif'""", con)
    rf = pd.read_sql("""select m.ret_1y from fund_metrics m join funds f on f.code=m.fund_code
                        where f.category='Para Piyasası' and coalesce(f.status,'aktif')='aktif' and m.ret_1y is not null""", con)["ret_1y"].median()
    m = m[m["vol"] > 0.001]
    m["sharpe"] = (m["ret_1y"] - rf) / m["vol"]
    low = m["vol"] < 0.05
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.scatter(m.loc[~low, "vol"], m.loc[~low, "sharpe"], s=8, color=BLUE, alpha=0.6, lw=0, label="Volatilite ≥ %5 (Sharpe hesaplanır)")
    ax.scatter(m.loc[low, "vol"], m.loc[low, "sharpe"], s=8, color=ORANGE, alpha=0.7, lw=0, label="Volatilite < %5 (Sharpe hesaplanmaz)")
    ax.axvline(0.05, color=MUTED, ls="--", lw=1)
    ax.set_xscale("log")
    pct_axis(ax, "x")
    ax.set_xlabel("1 yıllık volatilite (log)")
    ax.set_ylabel("Sharpe oranı (sınırsız)")
    ax.set_title(f"Sharpe oranı ve volatilite (risksiz getiri %{rf * 100:.1f})".replace(".", ","))
    ax.legend(fontsize=7.5, loc="upper right")
    save(fig, "sekil_3_2_sharpe_vol.png")


# --- 5. Öneri sistemi ----------------------------------------------------------------------

def risk_getiri(con):
    latest = pd.Timestamp(con.execute("select max(as_of) from fund_metrics").fetchone()[0])
    cut = (latest - timedelta(days=7)).date().isoformat()
    m = pd.read_sql(f"""select f.risk_level, m.ret_1y from fund_metrics m join funds f on f.code=m.fund_code
                        where f.risk_level is not null and m.ret_1y is not null and m.as_of >= '{cut}'
                        and coalesce(f.status,'aktif')='aktif'""", con)
    g = m.groupby("risk_level")["ret_1y"].agg(["median", "size"])
    fig, ax = plt.subplots(figsize=(6, 2.8))
    ax.bar(g.index.astype(int), g["median"], color=BLUE, width=0.6)
    for x, (v, n) in zip(g.index.astype(int), g.values):
        ax.text(x, v + 0.01, f"%{v * 100:.0f}\n({int(n)} fon)", ha="center", va="bottom", fontsize=7, color=MUTED)
    pct_axis(ax)
    ax.set_ylim(0, g["median"].max() * 1.3)
    ax.set_xlabel("TEFAS risk değeri")
    ax.set_ylabel("Medyan 1 yıllık getiri")
    ax.set_title("Risk değerine göre son 1 yılın medyan getirisi")
    save(fig, "sekil_5_1_risk_getiri.png")


def kayan_pencere(con):
    w = pd.read_sql("select profile, start_date, portfolio_return - benchmark_return excess from backtest_windows where qualified=0",
                    con, parse_dates=["start_date"])
    fig, ax = plt.subplots(figsize=(7, 3))
    for p, color, label in [("temkinli", BLUE, "Temkinli"), ("dengeli", ORANGE, "Dengeli"), ("agresif", AQUA, "Agresif")]:
        s = w[w["profile"] == p].sort_values("start_date")
        ax.plot(s["start_date"], s["excess"], color=color, lw=2, marker="o", ms=3, label=label)
    ax.axhline(0, color=MUTED, lw=0.8)
    pct_axis(ax)
    date_axis(ax, "%m.%Y", months=3)
    ax.set_ylabel("Fazla getiri (12 ay)")
    ax.set_xlabel("Seçim ayı")
    ax.set_title("Kayan pencereli test: örnek portföy eksi para piyasası medyanı")
    ax.legend(fontsize=7.5, ncol=3)
    save(fig, "sekil_5_2_kayan_pencere.png")


# --- 6. ML -------------------------------------------------------------------------------

def aylik_hata(con):
    import json

    row = con.execute("select payload from ml_reports order by created_at desc, id desc limit 1").fetchone()
    if not row:
        print("ml_reports boş, sekil_6_1 atlandı")
        return
    m = pd.DataFrame(json.loads(row[0])["monthly"])
    m["date"] = pd.to_datetime(m["date"])
    fig, ax = plt.subplots(figsize=(7, 3))
    for model, color, label in [("lightgbm", BLUE, "LightGBM"), ("drift", ORANGE, "Drift"), ("momentum", AQUA, "Momentum"), ("sifir", YELLOW, "Sıfır")]:
        s = m[m["model"] == model].sort_values("date")
        ax.plot(s["date"], s["mae_excess"], color=color, lw=1.8, label=label)
    pct_axis(ax)
    date_axis(ax, "%m.%Y", months=3)
    ax.set_ylabel("Fazla getiri MAE")
    ax.set_title("Test dönemi: ay ay tahmin hatası (düşük olan iyi)")
    ax.legend(fontsize=7.5, ncol=4)
    save(fig, "sekil_6_1_aylik_hata.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path())
    prices = pd.read_sql("select fund_code code, date, price from prices", con, parse_dates=["date"])
    mimari()
    fon_sayisi(prices)
    spk_fonlari(prices)
    pazartesi(prices)
    sharpe_vol(con)
    risk_getiri(con)
    kayan_pencere(con)
    aylik_hata(con)


if __name__ == "__main__":
    main()
