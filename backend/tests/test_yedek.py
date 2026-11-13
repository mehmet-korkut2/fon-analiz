import gzip
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
    assert b.name.startswith("fon_") and b.name.endswith("_sunum_öncesi.db.gz")
    assert gzip.open(b).read(16) == b"SQLite format 3\x00"  # gzip ile sıkıştırılmış SQLite
    assert yedek.check(b)["counts"] == {"funds": 2, "prices": 1, "sanal_emirler": 3}  # sanal portföy dahil

    # veritabanı bozuldu / değişti
    con = sqlite3.connect(db)
    con.execute("DELETE FROM funds")
    con.execute("DELETE FROM sanal_emirler")
    con.commit()
    con.close()

    safety = yedek.restore(b, db, dest)
    assert count(db, "funds") == 2 and count(db, "sanal_emirler") == 3
    assert safety.name.startswith(yedek.SAFETY_PREFIX) and safety.name.endswith(".db.gz")
    with yedek.opened(safety) as raw:
        assert count(raw, "funds") == 0
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


def test_stats_and_compression_shrinks(tmp_path):
    db, dest = tmp_path / "fon.db", tmp_path / "backups"
    make_db(db)
    con = sqlite3.connect(db)
    con.executemany("INSERT INTO prices VALUES (?, ?)", [(f"2026-01-{i % 28 + 1:02d}", 1.0) for i in range(20000)])
    con.commit()
    con.close()
    r = yedek.backup_with_stats(db, dest)
    assert r.path.suffixes[-2:] == [".db", ".gz"] and r.seconds >= 0
    assert r.size_bytes == r.path.stat().st_size and r.size_bytes < r.raw_bytes / 3
    assert not list(dest.glob("*.tmp"))  # geçici dosya kalmadı
    plain = yedek.backup_with_stats(db, dest, compress=False)
    assert plain.path.suffix == ".db" and plain.size_bytes == plain.raw_bytes


def test_restore_old_uncompressed_backup_and_list_both(tmp_path):
    db, dest = tmp_path / "fon.db", tmp_path / "backups"
    make_db(db, funds=("AAA", "BBB"))
    old = yedek.backup(db, dest, compress=False)  # önceki sürümün .db yedeği
    time.sleep(0.05)
    new = yedek.backup(db, dest)
    assert yedek.list_backups(dest) == [old, new]
    con = sqlite3.connect(db)
    con.execute("DELETE FROM funds")
    con.commit()
    con.close()
    yedek.restore(old, db, dest)
    assert count(db, "funds") == 2


def test_corrupt_gzip_rejected(tmp_path):
    db, dest = tmp_path / "fon.db", tmp_path / "backups"
    make_db(db)
    b = yedek.backup(db, dest)
    b.write_bytes(b.read_bytes()[:40])  # yarım kalmış dosya
    with pytest.raises(yedek.YedekHata):
        yedek.restore(b, db, dest)
    assert count(db, "funds") == 1


def test_favorites_and_accounts_included_in_backup(tmp_path):
    db, dest = tmp_path / "fon.db", tmp_path / "backups"
    make_db(db)
    con = sqlite3.connect(db)
    con.executescript("CREATE TABLE users (id INTEGER); CREATE TABLE favorites (user_id INTEGER, fund_code TEXT);"
                      "INSERT INTO users VALUES (1); INSERT INTO favorites VALUES (1, 'AAA'), (1, 'BBB');")
    con.commit()
    con.close()
    b = yedek.backup(db, dest)
    assert yedek.check(b)["counts"]["favorites"] == 2 and yedek.check(b)["counts"]["users"] == 1
    con = sqlite3.connect(db)
    con.execute("DELETE FROM favorites")
    con.commit()
    con.close()
    yedek.restore(b, db, dest)
    assert count(db, "favorites") == 2
