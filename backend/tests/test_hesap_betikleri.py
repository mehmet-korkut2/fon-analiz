"""Yerel hesap yönetimi: scripts/sifre_sifirla.py ve scripts/hesaplar.py (conftest'in geçici veritabanında)."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import settings
from app.database import SessionLocal, init_db
from app.main import app
from app.models import LoginThrottle, User, UserSession
from app.services import auth
from scripts import hesaplar, sifre_sifirla

OLD, NEW = "eski-sifre-123", "yeni-sifre-456"


@pytest.fixture
def db():
    init_db()
    with SessionLocal() as s:
        for m in (UserSession, LoginThrottle, User):
            s.execute(delete(m))
        s.commit()
        yield s


def asker(*answers):
    """getpass yerine: sırayla cevap verir, sorulan istemleri kaydeder."""
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return answers[len(calls) - 1]

    ask.calls = calls
    return ask


def make_user(db, email="ali@ornek.com", name="Ali"):
    return auth.register(db, email, OLD, name).user


def test_reset_password_closes_all_sessions_and_clears_lockout(db):
    u = make_user(db)
    tokens = [auth.create_session(db, u) for _ in range(3)]
    for _ in range(auth.EMAIL_THRESHOLD):
        auth.record_failure(db, u.email, "10.0.0.1")
    with pytest.raises(auth.AuthHata):
        auth.check_throttle(db, u.email, None)  # beklemede
    before = u.password_changed_at
    user, closed = auth.reset_password(db, "ALI@ornek.com ", NEW)
    assert closed == 3 and db.scalar(select(func.count()).select_from(UserSession)) == 0
    assert all(auth.user_for_token(db, t) is None for t in tokens)
    auth.check_throttle(db, u.email, None)  # bekleme kalktı
    assert user.password_hash.startswith("$argon2id$") and user.password_changed_at >= before
    assert auth.verify_password(user.password_hash, NEW) and not auth.verify_password(user.password_hash, OLD)
    assert auth.login(db, u.email, NEW, None).id == u.id


def test_reset_password_rules_and_unknown_email(db):
    make_user(db)
    with pytest.raises(auth.AuthHata, match="en az 8"):
        auth.reset_password(db, "ali@ornek.com", "kisa")
    with pytest.raises(auth.AuthHata, match="hesap yok"):
        auth.reset_password(db, "yok@ornek.com", NEW)
    assert auth.login(db, "ali@ornek.com", OLD, None)  # değişmedi


def test_script_success_hides_password_and_logs_out_api_session(db, capsys):
    make_user(db)
    c = TestClient(app)
    c.headers["X-Requested-With"] = "XMLHttpRequest"
    assert c.post("/api/auth/giris", json={"email": "ali@ornek.com", "password": OLD}).status_code == 200
    assert c.get("/api/auth/ben").json()["user"] is not None
    ask = asker(NEW, NEW)
    assert sifre_sifirla.main(["--eposta", "Ali@Ornek.com"], ask=ask) == 0
    out = capsys.readouterr()
    assert "Şifre değiştirildi: ali@ornek.com" in out.out and "Kapatılan oturum: 1" in out.out
    assert NEW not in out.out + out.err and len(ask.calls) == 2 and NEW not in "".join(ask.calls)
    assert c.get("/api/auth/ben").json()["user"] is None  # tarayıcıdaki oturum kapandı
    assert c.post("/api/auth/giris", json={"email": "ali@ornek.com", "password": OLD}).status_code == 401
    assert c.post("/api/auth/giris", json={"email": "ali@ornek.com", "password": NEW}).status_code == 200


@pytest.mark.parametrize("answers,msg", [
    ((NEW, "farkli-sifre-789"), "aynı değil"),
    (("kisa", "kisa"), "en az 8"),
    (("x" * 129, "x" * 129), "en çok 128"),
])
def test_script_rejects_and_keeps_old_password(db, capsys, answers, msg):
    make_user(db)
    assert sifre_sifirla.main(["--eposta", "ali@ornek.com"], ask=asker(*answers)) == 1
    err = capsys.readouterr().err
    assert msg in err and "değişmedi" in err
    assert auth.login(db, "ali@ornek.com", OLD, None)


def test_script_unknown_email_does_not_ask(db, capsys):
    ask = asker(NEW, NEW)
    assert sifre_sifirla.main(["--eposta", "yok@ornek.com"], ask=ask) == 1
    assert ask.calls == [] and "kayıtlı hesap yok" in capsys.readouterr().err


def test_script_cancel(db, capsys):
    make_user(db)

    def ask(_):
        raise KeyboardInterrupt

    assert sifre_sifirla.main(["--eposta", "ali@ornek.com"], ask=ask) == 1
    assert "Vazgeçildi" in capsys.readouterr().err
    assert auth.login(db, "ali@ornek.com", OLD, None)


def test_accounts_list_never_shows_password_info(db, capsys):
    assert hesaplar.main() == 0 and "Kayıtlı hesap yok" in capsys.readouterr().out
    make_user(db, "ali@ornek.com", "Ali")
    make_user(db, "ayse@ornek.com", "Ayşe Yılmaz")
    rows = auth.list_accounts(db)
    assert [set(r) for r in rows] == [{"email", "name", "created_at"}] * 2
    assert [r["email"] for r in rows] == ["ali@ornek.com", "ayse@ornek.com"]
    assert hesaplar.main() == 0
    out = capsys.readouterr().out
    assert "ali@ornek.com" in out and "Ayşe Yılmaz" in out and "2 hesap" in out
    assert f"{datetime.now():%Y}" in out
    hashes = list(db.scalars(select(User.password_hash)))
    assert "$argon2" not in out and OLD not in out and not any(h in out for h in hashes)
    assert settings.cookie_name not in out
