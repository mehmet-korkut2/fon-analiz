"""Kullanıcı hesabı, şifre ve oturum (güvenlik kararları ve tehdit/önlem tablosu: docs/rapor/03_backend_ve_metrikler.md, 3.7).

- Şifre: Argon2id (argon2-cffi, RFC 9106 önerilen düşük bellek profili). Düz şifre hiçbir yerde saklanmaz
  ve loglanmaz. Kural: 8-128 karakter (üst sınır, çok uzun şifreyle hash'i yavaşlatma saldırısına karşı).
- Oturum: rastgele 256 bitlik belirteç HttpOnly çerezde; veritabanında yalnızca SHA-256 özeti. Çıkışta,
  şifre değişikliğinde (diğer oturumlar) ve hesap silinince oturumlar silinir. Süre: settings.session_days.
- Kaba kuvvet: e-posta ve IP başına art arda hatalı giriş sayacı (login_throttle). Eşik aşılınca 30 sn
  bekleme; her yeni hata süreyi ikiye katlar (en çok 15 dk). Başarılı giriş e-posta sayacını sıfırlar.
- Hata mesajı tek: "E-posta ya da şifre hatalı." Kayıtlı olmayan e-postada da bir hash doğrulanır
  (yanıt süresinden e-postanın kayıtlı olup olmadığı anlaşılmasın).
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Favorite,
    LoginThrottle,
    RiskProfile,
    SanalAyar,
    SanalDeger,
    SanalEmir,
    User,
    UserSession,
)

PASSWORD_MIN, PASSWORD_MAX = 8, 128
NAME_MAX = 100
EMAIL_THRESHOLD, IP_THRESHOLD = 5, 20  # bu kadar art arda hatadan sonra bekleme başlar
BASE_LOCK = timedelta(seconds=30)
MAX_LOCK = timedelta(minutes=15)
FAILURE_WINDOW = timedelta(minutes=15)  # son hatadan bu kadar sonra sayaç sıfırlanır
LOGIN_ERROR = "E-posta ya da şifre hatalı."
# ".example" uzantılı adresler gerçek olamaz (RFC 2606; ".test" e-posta doğrulayıcısınca reddedilir). Uçtan uca
# testin geçici hesapları bunu kullanır ve giriş öncesinden kalan sanal portföyü devralmaz.
TEST_DOMAIN_SUFFIX = ".example"

_hasher = PasswordHasher()  # Argon2id, t=3, m=64 MiB, p=4
_DUMMY_HASH = _hasher.hash("zamanlama-esitleme-icin-sahte-sifre")


class AuthHata(ValueError):
    """Kullanıcıya gösterilecek hata. status: HTTP kodu."""

    def __init__(self, message: str, status: int = 400, retry_after: int | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def now() -> datetime:
    return datetime.now()


# --- şifre ----------------------------------------------------------------------------------------

def check_password_rule(password: str) -> None:
    if not isinstance(password, str) or len(password) < PASSWORD_MIN:
        raise AuthHata(f"Şifre en az {PASSWORD_MIN} karakter olmalı.", 422)
    if len(password) > PASSWORD_MAX:
        raise AuthHata(f"Şifre en çok {PASSWORD_MAX} karakter olabilir.", 422)


def hash_password(password: str) -> str:
    check_password_rule(password)
    return _hasher.hash(password)


def verify_password(hash_: str, password: str) -> bool:
    try:
        return _hasher.verify(hash_, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


# --- oturum ---------------------------------------------------------------------------------------

def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    """Yeni oturum; çereze yazılacak belirteci döner (veritabanında yalnızca özeti)."""
    token = secrets.token_urlsafe(32)
    t = now()
    db.add(UserSession(token_hash=_digest(token), user_id=user.id, created_at=t, last_seen_at=t,
                       expires_at=t + timedelta(days=settings.session_days)))
    db.commit()
    return token


def user_for_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    s = db.scalars(select(UserSession).where(UserSession.token_hash == _digest(token))).first()
    if s is None:
        return None
    t = now()
    if s.expires_at <= t:
        db.delete(s)
        db.commit()
        return None
    if s.last_seen_at is None or t - s.last_seen_at > timedelta(minutes=5):  # her istekte yazmamak için
        s.last_seen_at = t
        db.commit()
    return db.get(User, s.user_id)


def end_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == _digest(token)))
        db.commit()


def end_other_sessions(db: Session, user: User, keep_token: str | None = None) -> int:
    q = delete(UserSession).where(UserSession.user_id == user.id)
    if keep_token:
        q = q.where(UserSession.token_hash != _digest(keep_token))
    n = db.execute(q).rowcount
    db.commit()
    return n


# --- kaba kuvvet koruması -------------------------------------------------------------------------

def _keys(email: str, ip: str | None) -> list[tuple[str, int]]:
    keys = [(f"email:{email}", EMAIL_THRESHOLD)]
    if ip:
        keys.append((f"ip:{ip}", IP_THRESHOLD))
    return keys


def _row(db: Session, key: str) -> LoginThrottle:
    r = db.get(LoginThrottle, key)
    if r is None:
        r = LoginThrottle(key=key, failures=0)
        db.add(r)
    return r


def check_throttle(db: Session, email: str, ip: str | None) -> None:
    t = now()
    for key, _ in _keys(email, ip):
        r = db.get(LoginThrottle, key)
        if r and r.locked_until and r.locked_until > t:
            wait = int((r.locked_until - t).total_seconds()) + 1
            raise AuthHata(f"Çok fazla hatalı deneme. {wait} saniye sonra tekrar deneyin.", 429, retry_after=wait)


def record_failure(db: Session, email: str, ip: str | None) -> None:
    t = now()
    for key, threshold in _keys(email, ip):
        r = _row(db, key)
        if r.last_failure_at and t - r.last_failure_at > FAILURE_WINDOW:
            r.failures = 0
        r.failures = (r.failures or 0) + 1
        r.last_failure_at = t
        if r.failures >= threshold:
            lock = min(BASE_LOCK * 2 ** (r.failures - threshold), MAX_LOCK)
            r.locked_until = t + lock
    db.commit()


def clear_failures(db: Session, email: str) -> None:
    db.execute(delete(LoginThrottle).where(LoginThrottle.key == f"email:{email}"))
    db.commit()


# --- hesap ----------------------------------------------------------------------------------------

@dataclass
class Registered:
    user: User
    migrated_portfolio: bool


def register(db: Session, email: str, password: str, name: str) -> Registered:
    email = normalize_email(email)
    name = (name or "").strip()
    if not name:
        raise AuthHata("Ad boş olamaz.", 422)
    if len(name) > NAME_MAX:
        raise AuthHata(f"Ad en çok {NAME_MAX} karakter olabilir.", 422)
    pw_hash = hash_password(password)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise AuthHata("Bu e-posta adresiyle kayıtlı bir hesap var.", 409)
    real = ~User.email.like(f"%{TEST_DOMAIN_SUFFIX}")
    first = not email.endswith(TEST_DOMAIN_SUFFIX) and db.scalar(select(func.count()).select_from(User).where(real)) == 0
    user = User(email=email, password_hash=pw_hash, full_name=name, password_changed_at=now(), last_login_at=now())
    db.add(user)
    db.flush()
    migrated = claim_orphan_portfolio(db, user) if first else False
    db.commit()
    return Registered(user, migrated)


def claim_orphan_portfolio(db: Session, user: User) -> bool:
    """Kullanıcı girişinden önceki (sahipsiz) sanal portföyü bu kullanıcıya aktarır. İlk hesapta çağrılır."""
    ayar = db.scalars(select(SanalAyar).where(SanalAyar.user_id.is_(None))).first()
    orders = db.execute(update(SanalEmir).where(SanalEmir.user_id.is_(None)).values(user_id=user.id)).rowcount
    if ayar is not None:
        ayar.user_id = user.id
    return ayar is not None or orders > 0


def login(db: Session, email: str, password: str, ip: str | None) -> User:
    email = normalize_email(email)
    check_throttle(db, email, ip)
    user = db.scalars(select(User).where(User.email == email)).first()
    ok = verify_password(user.password_hash if user else _DUMMY_HASH, password or "")
    if user is None or not ok:
        record_failure(db, email, ip)
        raise AuthHata(LOGIN_ERROR, 401)
    clear_failures(db, email)
    if _hasher.check_needs_rehash(user.password_hash):  # parametreler değiştiyse yeni hash
        user.password_hash = _hasher.hash(password)
    user.last_login_at = now()
    db.commit()
    return user


def change_password(db: Session, user: User, current: str, new: str, keep_token: str | None) -> None:
    if not verify_password(user.password_hash, current or ""):
        raise AuthHata("Mevcut şifre hatalı.", 400)
    if current == new:
        raise AuthHata("Yeni şifre mevcut şifreyle aynı olamaz.", 422)
    user.password_hash = hash_password(new)
    user.password_changed_at = now()
    db.commit()
    end_other_sessions(db, user, keep_token)


def delete_account(db: Session, user: User, password: str) -> None:
    """Hesabı ve bütün kişisel verisini siler (profil, sanal portföy, favoriler, oturumlar)."""
    if not verify_password(user.password_hash, password or ""):
        raise AuthHata("Şifre hatalı.", 400)
    uid = user.id
    for model in (SanalDeger, SanalEmir, SanalAyar, Favorite, RiskProfile, UserSession):
        db.execute(delete(model).where(model.user_id == uid))
    db.execute(delete(LoginThrottle).where(LoginThrottle.key == f"email:{user.email}"))
    db.delete(user)
    db.commit()


# --- yerel yönetim (scripts/sifre_sifirla.py, scripts/hesaplar.py) ---------------------------------

def reset_password(db: Session, email: str, new: str) -> tuple[User, int]:
    """Bilgisayardan şifre sıfırlama (e-posta altyapısı yok). Mevcut şifre istenmez; bu yüzden yalnızca
    veritabanına erişimi olan (bilgisayarın sahibi) çalıştırabilir. Kurala uyar, kullanıcının bütün oturumlarını
    kapatır ve hatalı giriş sayacını sıfırlar. Dönen değer: kullanıcı ve kapatılan oturum sayısı."""
    email = normalize_email(email)
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None:
        raise AuthHata(f"{email} adresiyle kayıtlı hesap yok.", 404)
    user.password_hash = hash_password(new)
    user.password_changed_at = now()
    db.commit()
    closed = end_other_sessions(db, user)
    clear_failures(db, email)
    return user, closed


def list_accounts(db: Session) -> list[dict]:
    """Hesaplar: yalnızca e-posta, ad ve oluşturma tarihi (şifre bilgisi hiçbir zaman döndürülmez)."""
    rows = db.execute(select(User.email, User.full_name, User.created_at).order_by(User.created_at, User.id)).all()
    return [{"email": e, "name": n, "created_at": c} for e, n, c in rows]
