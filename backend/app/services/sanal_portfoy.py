"""Sanal portföy: hayali parayla fon alıp satma (ileriye dönük) ve "Ya o zaman alsaydım?" (geriye dönük).

Tek kullanıcı, kullanıcı girişi yok; veriler yerel veritabanında (sanal_portfoy, sanal_emirler,
sanal_degerler). Gerçek alım satım yapılmaz.

İleriye dönük mod, TEFAS kurallarına yakın çalışır:
- Emir günü: hafta sonu ya da fonun son işlem saatinden (sonIsSaat) sonra verilen emir ertesi iş günü sayılır.
- Valör: alışta fonGeriAlisValor, satışta fonSatisValor (TEFAS profili; tefas_client'taki not). Emir,
  emir gününe valör kadar iş günü eklenen günün fiyatından gerçekleşir. O gün tatilse (fiyat yoksa)
  sonraki ilk işlem gününün fiyatı kullanılır. Valör bilgisi yoksa ertesi iş günü.
- İleri fiyat: emir verilirken hedef günün fiyatı zaten biliniyorsa (veritabanında varsa) emir bir
  sonraki iş gününe kayar. Böylece bilinen bir fiyattan işlem yapılamaz.
- Alışta tutar emir verilince ayrılır (bloke); pay adedi tam sayıdır, artan tutar nakde döner.
  Satışta pay adedi girilir; bekleyen satıştaki paylar yeniden satılamaz.
- Komisyon, stopaj ve gerçek TEFAS'taki tutar/adet sınırları yoktur.
- SPK kararıyla işleme kapatılan ve eski verili (son fiyatı 7 günden eski) fonlar alınamaz.

Nakit, pozisyonlar ve maliyet her seferinde emir kayıtlarından hesaplanır; ayrıca bakiye saklanmaz.
Fiyatlar metriklerdeki gibi tek günlük hatalardan arındırılır (data_quality.drop_one_day_glitches);
veritabanındaki fiyat değiştirilmez.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Fund, Price, SanalAyar, SanalDeger, SanalEmir
from app.services import recommender
from app.services.data_quality import drop_one_day_glitches
from app.services.fund_status import STATUS_ACTIVE
from app.services.metrics_job import STALE_AFTER_DAYS

DEFAULT_BALANCE = 100_000.0
MIN_BALANCE, MAX_BALANCE = 1_000.0, 100_000_000.0
DEFAULT_VALOR = 1  # valör bilgisi yoksa ertesi iş günü
MAX_COMPARE = 4
ANNUALIZE_MIN_DAYS = 360  # yaklaşık 1 yıldan kısa dönemde yıllıklandırma yanıltıcı

ALIS, SATIS = "alis", "satis"
BEKLIYOR, GERCEKLESTI, IPTAL = "bekliyor", "gerceklesti", "iptal"


class SanalHata(ValueError):
    """Kullanıcıya gösterilecek doğrulama hatası (API 400 döner)."""


def tl(v: float, digits: int = 2) -> str:
    """Türkçe biçim: 12.345,67 TL"""
    s = f"{v:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} TL"


# --- İş günü ve valör ---------------------------------------------------------------

def next_business_day(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def add_business_days(d: date, n: int) -> date:
    for _ in range(n):
        d = next_business_day(d)
    return d


def order_day(now: datetime, cutoff: str | None) -> date:
    """Emrin sayıldığı iş günü: hafta sonu ya da son işlem saatinden sonra verilen emir ertesi iş günü."""
    d = now.date()
    if d.weekday() >= 5:
        return next_business_day(d)
    if cutoff:
        h, m = (int(x) for x in cutoff.split(":"))
        if now.time() > time(h, m):
            return next_business_day(d)
    return d


def target_date(day: date, valor: int, last_price: date | None) -> date:
    """Emir gününe valör kadar iş günü eklenir; o günün fiyatı zaten biliniyorsa sonraki iş günü (ileri fiyat)."""
    t = add_business_days(day, valor)
    if last_price is not None and t <= last_price:
        t = next_business_day(last_price)
    return t


# --- Veri yardımcıları ----------------------------------------------------------------

def latest_date(db: Session) -> date | None:
    return db.scalar(select(func.max(Price.date)))


def price_series(db: Session, code: str, since: date | None = None) -> pd.Series:
    """Fonun tarih indeksli, tek günlük hatalardan arındırılmış fiyat serisi."""
    stmt = select(Price.date, Price.price).where(Price.fund_code == code)
    if since is not None:
        stmt = stmt.where(Price.date >= since)
    rows = db.execute(stmt.order_by(Price.date)).all()
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series([p for _, p in rows], index=[d for d, _ in rows], dtype=float)
    return drop_one_day_glitches(s)


def first_on_or_after(s: pd.Series, d: date) -> tuple[date, float] | None:
    after = s[s.index >= d]
    return (after.index[0], float(after.iloc[0])) if len(after) else None


def settings(db: Session, today: date | None = None) -> SanalAyar:
    ayar = db.get(SanalAyar, 1)
    if ayar is None:
        ayar = SanalAyar(id=1, initial_balance=DEFAULT_BALANCE, start_date=today or date.today())
        db.add(ayar)
        db.commit()
    return ayar


def fund_buy_block(db: Session, fund: Fund) -> str | None:
    """Fon alınamıyorsa nedeni; alınabiliyorsa None."""
    if not fund.is_active:
        return "Bu fon TEFAS'ta işlem görmüyor."
    if (fund.status or STATUS_ACTIVE) != STATUS_ACTIVE:
        return fund.status_note or "Bu fon SPK kararıyla işleme kapatıldı."
    last = db.scalar(select(func.max(Price.date)).where(Price.fund_code == fund.code))
    overall = latest_date(db)
    if last is None:
        return "Bu fonun fiyat verisi yok."
    if overall and last < overall - timedelta(days=STALE_AFTER_DAYS):
        return f"Bu fonun verisi {last:%d.%m.%Y} tarihinden beri güncellenmiyor."
    return None


# --- Durum (emir kayıtlarından) --------------------------------------------------------

@dataclass
class Position:
    code: str
    units: int = 0
    cost: float = 0.0  # kalan payların ortalama maliyetle toplam maliyeti
    realized: float = 0.0  # satışlardan gerçekleşen kâr/zarar


@dataclass
class State:
    initial: float
    cash: float  # gerçekleşen işlemlerden sonra nakit (bloke dahil)
    reserved: float  # bekleyen alışlar için ayrılan tutar
    positions: dict[str, Position] = field(default_factory=dict)
    pending_sell_units: dict[str, int] = field(default_factory=dict)

    @property
    def available(self) -> float:
        return self.cash - self.reserved

    def sellable(self, code: str) -> int:
        p = self.positions.get(code)
        return (p.units if p else 0) - self.pending_sell_units.get(code, 0)


def orders(db: Session, status: str | None = None) -> list[SanalEmir]:
    stmt = select(SanalEmir).order_by(SanalEmir.id)
    if status:
        stmt = stmt.where(SanalEmir.status == status)
    return list(db.scalars(stmt))


def apply(state: State, o: SanalEmir) -> None:
    """Gerçekleşmiş bir emri duruma uygular (ortalama maliyet yöntemi)."""
    p = state.positions.setdefault(o.fund_code, Position(o.fund_code))
    if o.side == ALIS:
        state.cash -= o.exec_amount
        p.units += o.exec_units
        p.cost += o.exec_amount
    else:
        avg = p.cost / p.units if p.units else 0.0
        state.cash += o.exec_amount
        p.realized += o.exec_amount - avg * o.exec_units
        p.cost -= avg * o.exec_units
        p.units -= o.exec_units


def _executed_key(o: SanalEmir):
    return (o.exec_date, o.id)


def state(db: Session) -> State:
    """Gerçekleşen emirlere göre nakit ve pozisyonlar; bekleyen alışların tutarı ve satışların payı ayrılır."""
    ayar = settings(db)
    st = State(initial=ayar.initial_balance, cash=ayar.initial_balance, reserved=0.0)
    for o in sorted(orders(db, GERCEKLESTI), key=_executed_key):
        apply(st, o)
    for o in orders(db, BEKLIYOR):
        if o.side == ALIS:
            st.reserved += o.amount
        else:
            st.pending_sell_units[o.fund_code] = st.pending_sell_units.get(o.fund_code, 0) + o.units
    return st


# --- Emirler ----------------------------------------------------------------------------

def _new_order(db: Session, fund: Fund, side: str, now: datetime) -> SanalEmir:
    valor = fund.buy_valor if side == ALIS else fund.sell_valor
    known = valor is not None
    day = order_day(now, fund.cutoff_time)
    last = db.scalar(select(func.max(Price.date)).where(Price.fund_code == fund.code))
    t = target_date(day, valor if known else DEFAULT_VALOR, last)
    return SanalEmir(
        fund_code=fund.code, side=side, status=BEKLIYOR, created_at=now, order_date=day,
        valor=valor if known else DEFAULT_VALOR, valor_known=known, target_date=t,
        note=None if known else "TEFAS'ta valör bilgisi yok; ertesi iş günü fiyatı kullanılır.",
    )


def _fund(db: Session, code: str) -> Fund:
    fund = db.get(Fund, (code or "").strip().upper())
    if fund is None:
        raise SanalHata(f"{code} kodlu fon bulunamadı.")
    return fund


def place_buy(db: Session, code: str, amount: float, now: datetime | None = None) -> SanalEmir:
    now = now or datetime.now()
    fund = _fund(db, code)
    if not (amount and amount > 0 and math.isfinite(amount)):
        raise SanalHata("Alış tutarı sıfırdan büyük olmalı.")
    amount = round(float(amount), 2)
    if (reason := fund_buy_block(db, fund)) is not None:
        raise SanalHata(f"{fund.code} alınamaz: {reason}")
    st = state(db)
    if amount > st.available + 1e-9:
        raise SanalHata(f"Yetersiz nakit: kullanılabilir nakit {tl(st.available)} (bekleyen alışlar için ayrılan tutar düşüldü).")
    s = price_series(db, fund.code)
    if len(s) and amount < float(s.iloc[-1]):
        raise SanalHata(f"Tutar en az 1 pay alacak kadar olmalı (son fiyat: {tl(float(s.iloc[-1]), 4)}).")
    o = _new_order(db, fund, ALIS, now)
    o.amount = amount
    db.add(o)
    db.commit()
    process(db)
    return o


def place_sell(db: Session, code: str, units: int, now: datetime | None = None) -> SanalEmir:
    now = now or datetime.now()
    fund = _fund(db, code)
    if units is None or int(units) != units or units <= 0:
        raise SanalHata("Satılacak pay adedi pozitif bir tam sayı olmalı.")
    units = int(units)
    st = state(db)
    sellable = st.sellable(fund.code)
    if units > sellable:
        raise SanalHata(f"{fund.code} için satılabilir pay: {sellable:,} (bekleyen satışlar düşüldü).".replace(",", "."))
    o = _new_order(db, fund, SATIS, now)
    o.units = units
    db.add(o)
    db.commit()
    process(db)
    return o


def cancel(db: Session, order_id: int) -> SanalEmir:
    o = db.get(SanalEmir, order_id)
    if o is None:
        raise SanalHata("Emir bulunamadı.")
    if o.status != BEKLIYOR:
        raise SanalHata("Yalnızca bekleyen emirler iptal edilebilir.")
    o.status, o.note = IPTAL, "Kullanıcı iptal etti."
    db.commit()
    rebuild_values(db)
    return o


def reset(db: Session, initial_balance: float, today: date | None = None) -> SanalAyar:
    if not (initial_balance and MIN_BALANCE <= initial_balance <= MAX_BALANCE):
        raise SanalHata("Başlangıç bakiyesi 1.000 TL ile 100.000.000 TL arasında olmalı.")
    db.execute(delete(SanalEmir))
    db.execute(delete(SanalDeger))
    ayar = settings(db, today)
    ayar.initial_balance = round(float(initial_balance), 2)
    ayar.start_date = today or date.today()
    db.commit()
    rebuild_values(db)
    return ayar


def execute_pending(db: Session) -> int:
    """Hedef günü (ya da sonrası) için fiyatı gelen bekleyen emirleri gerçekleştirir."""
    done = 0
    pending = sorted(orders(db, BEKLIYOR), key=lambda o: (o.target_date, o.id))
    cache: dict[str, pd.Series] = {}
    for o in pending:
        s = cache.setdefault(o.fund_code, price_series(db, o.fund_code))
        hit = first_on_or_after(s, o.target_date)
        if hit is None:
            continue
        d, price = hit
        if o.side == ALIS:
            u = math.floor(o.amount / price + 1e-9)
            if u == 0:
                o.status, o.note = IPTAL, "Tutar gerçekleşme günündeki 1 pay fiyatından az; emir iptal edildi."
                continue
            o.exec_units, o.exec_amount = u, round(u * price, 2)
        else:
            o.exec_units, o.exec_amount = o.units, round(o.units * price, 2)
        o.exec_date, o.exec_price, o.status = d, price, GERCEKLESTI
        done += 1
    db.commit()
    return done


# --- Değer geçmişi ve kıyas ---------------------------------------------------------------

def mm_index(db: Session, start: date, end: date) -> pd.Series:
    """Para piyasası fonlarının medyanı, `start`ta 1 (öneri sistemindeki kıyasla aynı yöntem)."""
    codes = recommender.money_market_codes(db)
    if not codes:
        return pd.Series(dtype=float)
    wide = recommender.load_prices(db, codes, start - timedelta(days=STALE_AFTER_DAYS + 7))
    if wide.empty:
        return pd.Series(dtype=float)
    norm = recommender.normalized(wide, pd.Timestamp(start), pd.Timestamp(end))
    if norm.empty:
        return pd.Series(dtype=float)
    idx = norm.median(axis=1) / 100
    return pd.Series(idx.values, index=[t.date() for t in idx.index])


def rebuild_values(db: Session) -> int:
    """Başlangıç gününden son fiyat gününe kadar günlük portföy değerini yeniden yazar."""
    ayar = settings(db)
    db.execute(delete(SanalDeger))
    end = latest_date(db)
    if end is None or end < ayar.start_date:
        db.add(SanalDeger(date=ayar.start_date, cash=ayar.initial_balance, holdings=0.0,
                          total=ayar.initial_balance, benchmark=ayar.initial_balance))
        db.commit()
        return 1
    days = sorted({ayar.start_date, *db.scalars(select(Price.date).distinct().where(Price.date > ayar.start_date))})
    done = sorted(orders(db, GERCEKLESTI), key=_executed_key)
    codes = sorted({o.fund_code for o in done})
    series = {c: price_series(db, c, ayar.start_date - timedelta(days=STALE_AFTER_DAYS + 7)) for c in codes}
    mm = mm_index(db, ayar.start_date, end)
    mm_ff = mm.reindex(sorted(set(mm.index) | set(days))).ffill() if len(mm) else mm

    st = State(initial=ayar.initial_balance, cash=ayar.initial_balance, reserved=0.0)
    i = 0
    rows = []
    for d in days:
        while i < len(done) and done[i].exec_date <= d:
            apply(st, done[i])
            i += 1
        holdings = 0.0
        for c, p in st.positions.items():
            if p.units:
                s = series[c]
                upto = s[s.index <= d]
                holdings += p.units * (float(upto.iloc[-1]) if len(upto) else 0.0)
        bench = ayar.initial_balance * float(mm_ff.get(d)) if len(mm_ff) and pd.notna(mm_ff.get(d)) else None
        rows.append(SanalDeger(date=d, cash=round(st.cash, 2), holdings=round(holdings, 2),
                               total=round(st.cash + holdings, 2), benchmark=round(bench, 2) if bench else None))
    db.add_all(rows)
    db.commit()
    return len(rows)


def process(db: Session) -> dict:
    """Gece güncellemesinden ve her emirden sonra: bekleyen emirleri gerçekleştir, değerleri yeniden hesapla."""
    executed = execute_pending(db)
    n = rebuild_values(db)
    return {"executed": executed, "days": n}


# --- API için özet ----------------------------------------------------------------------

def _pct(a: float | None, b: float | None) -> float | None:
    return a / b - 1 if a is not None and b else None


def summary(db: Session) -> dict:
    if any(first_on_or_after(price_series(db, o.fund_code), o.target_date) for o in orders(db, BEKLIYOR)):
        process(db)  # betikle fiyat yüklendiyse bekleyen emirler hemen gerçekleşsin
    elif db.scalar(select(func.count()).select_from(SanalDeger)) == 0:
        rebuild_values(db)  # ilk açılış
    ayar = settings(db)
    st = state(db)
    all_orders = orders(db)
    funds = {f.code: f for f in db.scalars(select(Fund).where(Fund.code.in_({o.fund_code for o in all_orders})))}

    positions = []
    holdings = 0.0
    for c, p in sorted(st.positions.items()):
        if p.units == 0 and p.realized == 0:
            continue
        s = price_series(db, c)
        price, pdate = (float(s.iloc[-1]), s.index[-1]) if len(s) else (None, None)
        value = p.units * price if price is not None else 0.0
        holdings += value
        f = funds.get(c)
        positions.append({
            "code": c, "name": f.name if f else c, "category": f.category if f else None,
            "risk_level": f.risk_level if f else None, "status": (f.status if f else None) or STATUS_ACTIVE,
            "units": p.units, "avg_cost": p.cost / p.units if p.units else None, "cost": round(p.cost, 2),
            "price": price, "price_date": pdate, "value": round(value, 2),
            "pnl": round(value - p.cost, 2) if p.units else None, "pnl_pct": _pct(value, p.cost) if p.units else None,
            "realized": round(p.realized, 2), "sellable": st.sellable(c),
            "sell_valor": f.sell_valor if f else None,
        })

    values = [{"date": v.date, "total": v.total, "cash": v.cash, "holdings": v.holdings, "benchmark": v.benchmark}
              for v in db.scalars(select(SanalDeger).order_by(SanalDeger.date))]
    total = st.cash + holdings
    bench = values[-1]["benchmark"] if values else None

    def order_out(o: SanalEmir) -> dict:
        f = funds.get(o.fund_code)
        return {
            "id": o.id, "code": o.fund_code, "name": f.name if f else o.fund_code, "side": o.side, "status": o.status,
            "created_at": o.created_at, "order_date": o.order_date, "valor": o.valor, "valor_known": o.valor_known,
            "target_date": o.target_date, "amount": o.amount, "units": o.units, "exec_date": o.exec_date,
            "exec_price": o.exec_price, "exec_units": o.exec_units, "exec_amount": o.exec_amount, "note": o.note,
        }

    return {
        "initial_balance": ayar.initial_balance, "start_date": ayar.start_date, "as_of": latest_date(db),
        "total": round(total, 2), "cash": round(st.cash, 2), "reserved": round(st.reserved, 2),
        "available": round(st.available, 2), "holdings": round(holdings, 2),
        "pnl": round(total - ayar.initial_balance, 2), "pnl_pct": _pct(total, ayar.initial_balance),
        "realized": round(sum(p.realized for p in st.positions.values()), 2),
        "benchmark": bench, "benchmark_pct": _pct(bench, ayar.initial_balance),
        "positions": positions,
        "pending": [order_out(o) for o in all_orders if o.status == BEKLIYOR],
        "history": [order_out(o) for o in reversed(all_orders) if o.status != BEKLIYOR],
        "values": values,
    }


# --- "Ya o zaman alsaydım?" ----------------------------------------------------------------

def annualized(r: float, days: int) -> float | None:
    if days < ANNUALIZE_MIN_DAYS or r <= -1:
        return None
    return (1 + r) ** (365.25 / days) - 1


def what_if(db: Session, codes: list[str], when: date, amount: float) -> dict:
    """Seçilen gün (ya da sonraki ilk işlem günü) fiyatından alınıp bugüne kadar tutulsaydı.

    Pay kesirli kabul edilir (karşılaştırma için). Her fon kendi alış gününden son fiyatına kadar
    para piyasası medyanıyla da kıyaslanır.
    """
    codes = list(dict.fromkeys(c.strip().upper() for c in codes if c and c.strip()))
    if not codes:
        raise SanalHata("En az bir fon seçin.")
    if len(codes) > MAX_COMPARE:
        raise SanalHata(f"En fazla {MAX_COMPARE} fon karşılaştırılabilir.")
    if not (amount and amount > 0 and math.isfinite(amount)):
        raise SanalHata("Tutar sıfırdan büyük olmalı.")
    end = latest_date(db)
    if end is None:
        raise SanalHata("Veritabanında fiyat yok.")
    if when >= end:
        raise SanalHata(f"Tarih son fiyat gününden ({end:%d.%m.%Y}) önce olmalı.")
    first = db.scalar(select(func.min(Price.date)))
    if when < first:
        raise SanalHata(f"Fiyat verisi {first:%d.%m.%Y} tarihinden başlıyor.")

    mm = mm_index(db, when, end)
    funds_out, chart = [], {}
    for c in codes:
        f = db.get(Fund, c)
        if f is None:
            raise SanalHata(f"{c} kodlu fon bulunamadı.")
        s = price_series(db, c)
        hit = first_on_or_after(s, when)
        if hit is None:
            funds_out.append({"code": c, "name": f.name, "error": "Bu tarihten sonra fiyatı yok."})
            continue
        buy_date, buy_price = hit
        held = s[s.index >= buy_date]
        last_date, last_price = held.index[-1], float(held.iloc[-1])
        units = amount / buy_price
        value = units * last_price
        r = value / amount - 1
        days = (last_date - buy_date).days
        mm_f = mm_index(db, buy_date, last_date)
        mm_r = float(mm_f.iloc[-1] - 1) if len(mm_f) else None
        funds_out.append({
            "code": c, "name": f.name, "category": f.category, "risk_level": f.risk_level,
            "status": f.status or STATUS_ACTIVE, "status_note": f.status_note,
            "buy_date": buy_date, "buy_price": buy_price, "units": units, "last_date": last_date, "last_price": last_price,
            "value": round(value, 2), "pnl": round(value - amount, 2), "pnl_pct": r, "days": days,
            "annualized": annualized(r, days),
            "mm_value": round(amount * (1 + mm_r), 2) if mm_r is not None else None, "mm_pct": mm_r,
            "mm_annualized": annualized(mm_r, days) if mm_r is not None else None,
            "late_start": buy_date > next_business_day(when) + timedelta(days=STALE_AFTER_DAYS),
        })
        for d, p in held.items():
            chart.setdefault(d, {})[c] = round(units * p, 2)
    for d, v in mm.items():
        chart.setdefault(d, {})["mm"] = round(amount * float(v), 2)
    mm_r_all = float(mm.iloc[-1] - 1) if len(mm) else None
    return {
        "date": when, "amount": amount, "as_of": end, "funds": funds_out,
        "mm_pct": mm_r_all, "mm_value": round(amount * (1 + mm_r_all), 2) if mm_r_all is not None else None,
        "mm_start": mm.index[0] if len(mm) else None,
        "series": [{"date": d, **v} for d, v in sorted(chart.items())],
    }
