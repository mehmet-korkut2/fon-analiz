"""Kullanıcı girişi: kayıt, giriş, yanlış şifre, kaba kuvvet beklemesi, oturum, yetkisiz erişim, kullanıcılar
arası veri ayrımı, şifre değiştirme, CSRF, giriş öncesi sanal portföyün ilk hesaba aktarılması, hesap silme."""
from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Favorite, Fund, Price, RiskProfile, SanalAyar, SanalEmir, User, UserSession
from app.services import auth as A
from app.services import sanal_portfoy as S

PW = "dogru-sifre-123"
ANSWERS = {"q1": 2, "q2": 2, "q3": 2, "q4": 2, "q5": 2, "q6": 2, "q7": 2, "q8": 2}


@pytest.fixture
def Session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    S_ = sessionmaker(bind=engine)
    with S_() as db:
        db.add_all([Fund(code="HSA", name="HİSSE FONU", category="Hisse Senedi", risk_level=6, fund_type="YAT",
                         buy_valor=1, sell_valor=2, cutoff_time="17:45"),
                    Fund(code="PPA", name="PARA PİYASASI", category="Para Piyasası", risk_level=1, fund_type="YAT",
                         buy_valor=0, sell_valor=0)])
        for i, d in enumerate(pd.bdate_range("2026-09-01", "2026-10-09")):
            db.add_all([Price(fund_code="HSA", date=d.date(), price=1 + 0.001 * i),
                        Price(fund_code="PPA", date=d.date(), price=1.0012 ** i)])
        db.commit()

    def override():
        with S_() as s:
            yield s

    app.dependency_overrides[get_db] = override
    yield S_
    app.dependency_overrides.clear()


def client(csrf=True) -> TestClient:
    c = TestClient(app)
    if csrf:
        c.headers["X-Requested-With"] = "XMLHttpRequest"
    return c


def register(c, email="ali@ornek.com", password=PW, name="Ali"):
    return c.post("/api/auth/kayit", json={"email": email, "password": password, "name": name})


def login(c, email="ali@ornek.com", password=PW):
    return c.post("/api/auth/giris", json={"email": email, "password": password})


def answers():
    from app.services import risk_survey as rs

    return {q.id: 2 for q in rs.QUESTIONS}


# --- kayıt ve şifre saklama -----------------------------------------------------------------------

def test_register_sets_httponly_cookie_and_hashes_password(Session):
    c = client()
    r = register(c, email="  Ali@Ornek.com ")
    assert r.status_code == 201 and r.json()["user"]["email"] == "ali@ornek.com"
    cookie = r.headers["set-cookie"]
    assert settings.cookie_name in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/api" in cookie
    assert c.get("/api/auth/ben").json()["user"]["name"] == "Ali"
    with Session() as db:
        u = db.scalars(select(User)).one()
        assert u.password_hash.startswith("$argon2id$") and PW not in u.password_hash
        # veritabanının hiçbir yerinde düz şifre ya da düz oturum belirteci yok
        dump = "\n".join(db.connection().connection.iterdump())
        assert PW not in dump and c.cookies[settings.cookie_name] not in dump
        assert db.scalars(select(UserSession)).one().token_hash != c.cookies[settings.cookie_name]


@pytest.mark.parametrize("body,status,msg", [
    ({"email": "kisa@ornek.com", "password": "1234567", "name": "A"}, 422, "en az 8"),
    ({"email": "uzun@ornek.com", "password": "x" * 129, "name": "A"}, 422, "en çok 128"),
    ({"email": "bozuk-adres", "password": PW, "name": "A"}, 422, None),
    ({"email": "bos@ornek.com", "password": PW, "name": "  "}, 422, "Ad boş"),
])
def test_register_validation(Session, body, status, msg):
    r = client().post("/api/auth/kayit", json=body)
    assert r.status_code == status
    if msg:
        assert msg in r.json()["detail"]


def test_duplicate_email_case_insensitive(Session):
    assert register(client()).status_code == 201
    r = register(client(), email="ALI@ornek.com")
    assert r.status_code == 409


def test_password_of_exactly_8_chars_accepted(Session):
    assert register(client(), password="12345678").status_code == 201


# --- giriş, yanlış şifre, çıkış -------------------------------------------------------------------

def test_login_wrong_password_and_unknown_email_same_message(Session):
    register(client())
    c = client()
    ok = login(c)
    assert ok.status_code == 200 and c.get("/api/auth/ben").json()["user"]["email"] == "ali@ornek.com"
    wrong, unknown = login(client(), password="yanlis-sifre"), login(client(), email="yok@ornek.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"] == A.LOGIN_ERROR
    assert "set-cookie" not in wrong.headers


def test_logout_ends_session_server_side(Session):
    c = client()
    register(c)
    token = c.cookies[settings.cookie_name]
    assert c.post("/api/auth/cikis").status_code == 204
    assert c.get("/api/auth/ben").json()["user"] is None
    # eski belirteç (ör. çalınmış çerez) artık geçersiz
    stolen = client()
    stolen.cookies.set(settings.cookie_name, token)
    assert stolen.get("/api/auth/ben").json()["user"] is None
    assert stolen.get("/api/favoriler").status_code == 401


def test_login_rotates_token(Session):
    c = client()
    register(c)
    before = c.cookies[settings.cookie_name]
    login(c)
    assert c.cookies[settings.cookie_name] != before
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(UserSession)) == 1  # eski oturum kapandı


def test_expired_session_rejected(Session, monkeypatch):
    c = client()
    register(c)
    later = datetime.now() + timedelta(days=settings.session_days, minutes=1)
    monkeypatch.setattr(A, "now", lambda: later)
    assert c.get("/api/auth/ben").json()["user"] is None


# --- kaba kuvvet ----------------------------------------------------------------------------------

def test_brute_force_lockout_and_backoff(Session, monkeypatch):
    register(client())
    t = [datetime(2026, 11, 13, 12, 0, 0)]
    monkeypatch.setattr(A, "now", lambda: t[0])
    for _ in range(A.EMAIL_THRESHOLD):
        assert login(client(), password="yanlis-sifre").status_code == 401
    # eşik aşıldı: doğru şifre de beklemede reddedilir
    r = login(client())
    assert r.status_code == 429 and int(r.headers["Retry-After"]) == 31 and "saniye" in r.json()["detail"]
    t[0] += timedelta(seconds=31)
    assert login(client(), password="yanlis-sifre").status_code == 401  # 6. hata: bekleme ikiye katlanır
    r = login(client())
    assert r.status_code == 429 and int(r.headers["Retry-After"]) == 61
    t[0] += timedelta(seconds=61)
    assert login(client()).status_code == 200  # süre dolunca doğru şifre geçer, sayaç sıfırlanır
    assert login(client(), password="yanlis-sifre").status_code == 401
    assert login(client()).status_code == 200


def test_lockout_is_capped(Session, monkeypatch):
    register(client())
    t = [datetime(2026, 11, 13, 12, 0, 0)]
    monkeypatch.setattr(A, "now", lambda: t[0])
    with Session() as db:
        for _ in range(30):
            A.record_failure(db, "ali@ornek.com", None)
        r = db.get(A.LoginThrottle, "email:ali@ornek.com")
        assert r.locked_until - t[0] == A.MAX_LOCK


def test_ip_throttle_across_emails(Session, monkeypatch):
    t = [datetime(2026, 11, 13, 12, 0, 0)]
    monkeypatch.setattr(A, "now", lambda: t[0])
    for i in range(A.IP_THRESHOLD):  # aynı IP'den farklı e-postalar
        assert login(client(), email=f"x{i}@ornek.com", password="yanlis").status_code == 401
    assert login(client(), email="baska@ornek.com", password="yanlis").status_code == 429


# --- yetkisiz erişim ve herkese açık sayfalar -----------------------------------------------------

@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/sanal-portfoy", None),
    ("post", "/api/sanal-portfoy/emir", {"code": "HSA", "side": "alis", "amount": 1000}),
    ("delete", "/api/sanal-portfoy/emir/1", None),
    ("post", "/api/sanal-portfoy/sifirla", {"initial_balance": 5000}),
    ("get", "/api/favoriler", None),
    ("post", "/api/favoriler/HSA", None),
    ("get", "/api/profilim", None),
    ("post", "/api/profilim", {"answers": ANSWERS}),
    ("post", "/api/auth/sifre", {"current_password": PW, "new_password": "yeni-sifre-123"}),
    ("delete", "/api/auth/hesap", None),
])
def test_unauthorized_requires_login(Session, method, path, body):
    c = client()
    r = c.request(method.upper(), path, json=body) if body else getattr(c, method)(path)
    assert r.status_code == 401 and "giriş" in r.json()["detail"]


def test_public_pages_work_without_login(Session):
    c = client(csrf=False)
    assert c.get("/api/funds").status_code == 200
    assert c.get("/api/funds/HSA").status_code == 200
    assert c.get("/api/auth/ben").json() == {"user": None}
    assert c.post("/api/risk-profile", json={"answers": answers()}).status_code == 200  # anket herkese açık
    assert c.get("/api/sanal-portfoy/geriye", params={"funds": "HSA", "tarih": "2026-09-15"}).status_code == 200


def test_csrf_header_required_with_session_cookie(Session):
    c = client()
    register(c)
    bare = TestClient(app)
    bare.cookies.set(settings.cookie_name, c.cookies[settings.cookie_name])
    r = bare.post("/api/favoriler/HSA")
    assert r.status_code == 403 and "CSRF" in r.json()["detail"]
    assert bare.get("/api/favoriler").status_code == 200  # okuma serbest
    assert c.post("/api/favoriler/HSA").status_code == 204


# --- kullanıcılar arası veri ayrımı ---------------------------------------------------------------

def test_users_cannot_see_each_others_data(Session):
    a, b = client(), client()
    register(a, "a@ornek.com", name="A")
    register(b, "b@ornek.com", name="B")
    # A: emir, favori, profil
    oid = a.post("/api/sanal-portfoy/emir", json={"code": "HSA", "side": "alis", "amount": 10_000}).json()["pending"][0]["id"]
    assert a.post("/api/favoriler/HSA").status_code == 204
    assert a.post("/api/profilim", json={"answers": answers(), "qualified": True}).status_code == 200

    pb = b.get("/api/sanal-portfoy").json()
    assert pb["pending"] == [] and pb["reserved"] == 0 and pb["available"] == 100_000
    assert b.get("/api/favoriler").json() == []
    assert b.get("/api/profilim").json() is None
    # B, A'nın emrini iptal edemez; emrin varlığı da belli olmaz
    r = b.delete(f"/api/sanal-portfoy/emir/{oid}")
    assert r.status_code == 404 and r.json()["detail"] == "Emir bulunamadı."
    # B portföyünü sıfırlayınca A'nınki etkilenmez
    assert b.post("/api/sanal-portfoy/sifirla", json={"initial_balance": 5_000}).json()["total"] == 5_000
    pa = a.get("/api/sanal-portfoy").json()
    assert len(pa["pending"]) == 1 and pa["pending"][0]["id"] == oid and pa["reserved"] == 10_000
    assert [f["code"] for f in a.get("/api/favoriler").json()] == ["HSA"]
    assert a.get("/api/profilim").json()["qualified"] is True


def test_nightly_process_handles_each_user(Session):
    a, b = client(), client()
    register(a, "a@ornek.com")
    register(b, "b@ornek.com")
    a.post("/api/sanal-portfoy/emir", json={"code": "HSA", "side": "alis", "amount": 1_000})
    b.get("/api/sanal-portfoy")
    with Session() as db:
        r = S.process(db)
        assert r["users"] == 2
        ids = {u: S.state(db, u).reserved for u in db.scalars(select(User.id))}
        assert sorted(ids.values()) == [0, 1_000]


# --- profil ve favoriler --------------------------------------------------------------------------

def test_profile_saved_with_history_latest_wins(Session):
    c = client()
    register(c)
    assert c.get("/api/profilim").json() is None
    first = c.post("/api/profilim", json={"answers": answers()}).json()
    hi = {k: 4 for k in answers()}
    second = c.post("/api/profilim", json={"answers": hi, "qualified": True}).json()
    got = c.get("/api/profilim").json()
    assert got["answers"] == hi and got["result"]["score"] == second["result"]["score"] != first["result"]["score"]
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(RiskProfile)) == 2
    assert c.delete("/api/profilim").status_code == 204 and c.get("/api/profilim").json() is None


def test_favorites_add_remove_idempotent(Session):
    c = client()
    register(c)
    assert c.post("/api/favoriler/hsa").status_code == 204
    assert c.post("/api/favoriler/HSA").status_code == 204  # ikinci kez eklemek çoğaltmaz
    assert c.post("/api/favoriler/PPA").status_code == 204
    assert [f["code"] for f in c.get("/api/favoriler").json()] == ["PPA", "HSA"]
    assert c.post("/api/favoriler/YOK").status_code == 404
    assert c.delete("/api/favoriler/HSA").status_code == 204
    assert [f["code"] for f in c.get("/api/favoriler").json()] == ["PPA"]


# --- şifre değiştirme -----------------------------------------------------------------------------

def test_change_password_logs_out_other_sessions(Session):
    c, other = client(), client()
    register(c)
    login(other)
    r = c.post("/api/auth/sifre", json={"current_password": "yanlis", "new_password": "yeni-sifre-123"})
    assert r.status_code == 400 and "Mevcut şifre" in r.json()["detail"]
    assert c.post("/api/auth/sifre", json={"current_password": PW, "new_password": "kisa"}).status_code == 422
    assert c.post("/api/auth/sifre", json={"current_password": PW, "new_password": PW}).status_code == 422
    assert c.post("/api/auth/sifre", json={"current_password": PW, "new_password": "yeni-sifre-123"}).status_code == 200
    assert c.get("/api/auth/ben").json()["user"] is not None  # bu oturum sürer (yeni belirteçle)
    assert other.get("/api/auth/ben").json()["user"] is None  # diğer oturum kapandı
    assert login(client()).status_code == 401
    assert login(client(), password="yeni-sifre-123").status_code == 200


# --- giriş öncesi sanal portföyün aktarılması -----------------------------------------------------

def test_orphan_portfolio_moves_to_first_account_only(Session):
    with Session() as db:  # kullanıcı girişinden önceki tek kullanıcılı portföy (user_id boş)
        db.add(SanalAyar(id=1, user_id=None, initial_balance=250_000, start_date=date(2026, 10, 1)))
        db.add(SanalEmir(user_id=None, fund_code="HSA", side="alis", status="bekliyor", created_at=datetime(2026, 10, 1, 10),
                         order_date=date(2026, 10, 1), valor=1, target_date=date(2026, 10, 2), amount=20_000))
        db.commit()
    probe = client()  # uçtan uca testin geçici hesabı (.example) portföyü devralmaz
    assert register(probe, "uctan-uca-1@fonanaliz.example").json()["migrated_portfolio"] is False
    first = client()
    r = register(first, "ilk@ornek.com")
    assert r.json()["migrated_portfolio"] is True
    p = first.get("/api/sanal-portfoy").json()
    assert p["initial_balance"] == 250_000 and p["start_date"] == "2026-10-01"
    assert len(p["history"]) == 1 and p["history"][0]["status"] == "gerceklesti"  # fiyatı gelmişti, işlendi
    second = client()
    assert register(second, "ikinci@ornek.com").json()["migrated_portfolio"] is False
    p2 = second.get("/api/sanal-portfoy").json()
    assert p2["initial_balance"] == 100_000 and p2["history"] == []
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(SanalAyar).where(SanalAyar.user_id.is_(None))) == 0


# --- hesap silme ----------------------------------------------------------------------------------

def test_delete_account_removes_all_personal_data(Session):
    c, keep = client(), client()
    register(c)
    register(keep, "kalan@ornek.com")
    c.post("/api/sanal-portfoy/emir", json={"code": "HSA", "side": "alis", "amount": 1_000})
    c.post("/api/favoriler/HSA")
    c.post("/api/profilim", json={"answers": answers()})
    keep.post("/api/favoriler/PPA")
    assert c.request("DELETE", "/api/auth/hesap", json={"password": "yanlis"}).status_code == 400
    assert c.request("DELETE", "/api/auth/hesap", json={"password": PW}).status_code == 204
    assert c.get("/api/auth/ben").json()["user"] is None
    with Session() as db:
        uid = db.scalar(select(User.id).where(User.email == "kalan@ornek.com"))
        for model in (SanalEmir, Favorite, RiskProfile, UserSession, SanalAyar):
            assert all(r.user_id == uid for r in db.scalars(select(model))), model.__name__
        assert db.scalar(text("select count(*) from sanal_degerler where user_id != :u"), {"u": uid}) == 0
    assert register(client()).status_code == 201  # aynı e-postayla yeniden kayıt
