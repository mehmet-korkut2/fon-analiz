"""Veritabanı yedeği ve geri yükleme (scripts/yedekle.py, scripts/geri_yukle.py).

Yedek, SQLite'ın çevrim içi yedekleme API'siyle alınır: backend çalışırken de tutarlı bir kopya
çıkar. Tek dosya olduğu için fon verisi, metrikler, tahminler, sanal portföy ve son bilinen döviz
kurları birlikte yedeklenir. Yedekler proje kökündeki backups/ klasöründedir (git'e girmez).

Geri yüklemeden önce mevcut veritabanının da bir kopyası alınır (geri_yukleme_oncesi_*.db),
böylece yanlış yedek seçilirse geri dönülebilir.
"""
from __future__ import annotations

import socket
import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import settings

ROOT = Path(__file__).resolve().parents[3]  # proje kökü
BACKUP_DIR = ROOT / "backups"
BACKEND_DIR = Path(__file__).resolve().parents[2]
REQUIRED_TABLES = {"funds", "prices"}
PREFIX, SAFETY_PREFIX = "fon_", "geri_yukleme_oncesi_"


class YedekHata(Exception):
    pass


def db_file() -> Path:
    url = settings.database_url
    if not url.startswith("sqlite:///"):
        raise YedekHata("Yedekleme yalnızca yerel SQLite veritabanı için.")
    return (BACKEND_DIR / url.removeprefix("sqlite:///")).resolve()


def _copy(src: Path, dst: Path) -> None:
    """src veritabanını dst'ye kopyalar (SQLite yedekleme API'si; açık bağlantılar varken de tutarlı)."""
    s, d = sqlite3.connect(src), sqlite3.connect(dst)
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()


def check(path: Path) -> dict:
    """Dosya geçerli bir proje veritabanı mı: bütünlük denetimi ve tablo/kayıt sayıları."""
    if not path.is_file():
        raise YedekHata(f"Dosya bulunamadı: {path}")
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise YedekHata(f"Bütünlük denetimi başarısız: {path.name}")
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not REQUIRED_TABLES <= tables:
                raise YedekHata(f"{path.name} bu projenin veritabanı değil (funds/prices tablosu yok).")
            counts = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                      for t in ("funds", "prices", "sanal_emirler") if t in tables}
            last = con.execute("SELECT MAX(date) FROM prices").fetchone()[0]
        finally:
            con.close()
    except sqlite3.DatabaseError as e:
        raise YedekHata(f"{path.name} okunamadı: {e}") from e
    return {"counts": counts, "latest_price_date": last}


def backup(db: Path | None = None, dest: Path = BACKUP_DIR, label: str | None = None, prefix: str = PREFIX) -> Path:
    db = db or db_file()
    if not db.is_file():
        raise YedekHata(f"Veritabanı bulunamadı: {db}")
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (label or "")).strip("_")[:40]
    out = dest / f"{prefix}{stamp}{'_' + safe if safe else ''}.db"
    n = 1
    while out.exists():  # aynı saniyede ikinci yedek
        out = dest / f"{prefix}{stamp}_{n}.db"
        n += 1
    tmp = out.with_suffix(".tmp")
    _copy(db, tmp)
    check(tmp)
    tmp.replace(out)
    return out


def list_backups(dest: Path = BACKUP_DIR) -> list[Path]:
    """Yedekler, en yenisi sonda (geri yükleme öncesi güvenlik kopyaları dahil değil)."""
    if not dest.is_dir():
        return []
    return sorted((p for p in dest.glob(f"{PREFIX}*.db")), key=lambda p: p.stat().st_mtime)


def backend_running(port: int = 8000) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def restore(src: Path, db: Path | None = None, dest: Path = BACKUP_DIR) -> Path | None:
    """src yedeğini veritabanının yerine koyar; önce mevcut veritabanının güvenlik kopyasını alır.
    Dönen değer güvenlik kopyasının yolu (mevcut veritabanı yoksa None)."""
    db = db or db_file()
    check(src)
    safety = backup(db, dest, prefix=SAFETY_PREFIX) if db.is_file() else None
    _copy(src, db)
    check(db)
    return safety
