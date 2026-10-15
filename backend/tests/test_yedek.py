import sqlite3
import time

import pytest

from app.services import yedek


def make_db(path, funds=("AAA",), emir=0):
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE funds (code TEXT); CREATE TABLE prices (date TEXT, price REAL);"
                      "CREATE TABLE sanal_emirler (id INTEGER);")
    con.executemany("INSERT INTO funds VALUES (?)", [(f,) for f in funds])
    con.execute("INSERT INTO prices VALUES ('2026-10-14', 1.0)")
    con.executemany("INSERT INTO sanal_emirler VALUES (?)", [(i,) for i in range(emir)])
    con.commit()
    con.close()


def count(path, table):
    con = sqlite3.connect(path)
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        con.close()


def test_backup_restore_roundtrip_with_safety_copy(tmp_path):
    db, dest = tmp_path / "fon.db", tmp_path / "backups"
    make_db(db, funds=("AAA", "BBB"), emir=3)
    b = yedek.backup(db, dest, label="sunum öncesi!")
    assert b.name.startswith("fon_") and b.name.endswith("_sunum_öncesi.db")
    assert yedek.check(b)["counts"] == {"funds": 2, "prices": 1, "sanal_emirler": 3}  # sanal portföy dahil

    # veritabanı bozuldu / değişti
    con = sqlite3.connect(db)
    con.execute("DELETE FROM funds")
    con.execute("DELETE FROM sanal_emirler")
    con.commit()
    con.close()

    safety = yedek.restore(b, db, dest)
    assert count(db, "funds") == 2 and count(db, "sanal_emirler") == 3
    assert safety.name.startswith(yedek.SAFETY_PREFIX) and count(safety, "funds") == 0
    assert yedek.list_backups(dest) == [b]  # güvenlik kopyası listede değil


def test_list_backups_newest_last_and_latest_restore(tmp_path):
    db, dest = tmp_path / "fon.db", tmp_path / "backups"
    make_db(db, funds=("AAA",))
    first = yedek.backup(db, dest)
    time.sleep(0.05)
    con = sqlite3.connect(db)
    con.execute("INSERT INTO funds VALUES ('BBB')")
    con.commit()
    con.close()
    second = yedek.backup(db, dest)
    assert first != second and yedek.list_backups(dest) == [first, second]


def test_invalid_backup_rejected(tmp_path):
    db, dest = tmp_path / "fon.db", tmp_path / "backups"
    make_db(db)
    bad = tmp_path / "bozuk.db"
    bad.write_bytes(b"bu bir veritabani degil")
    with pytest.raises(yedek.YedekHata):
        yedek.restore(bad, db, dest)
    other = tmp_path / "baska.db"
    sqlite3.connect(other).execute("CREATE TABLE x (a)").connection.close()
    with pytest.raises(yedek.YedekHata, match="projenin veritabanı değil"):
        yedek.restore(other, db, dest)
    assert count(db, "funds") == 1  # mevcut veritabanı bozulmadı
    with pytest.raises(yedek.YedekHata, match="bulunamadı"):
        yedek.backup(tmp_path / "yok.db", dest)
