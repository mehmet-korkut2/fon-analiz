"""İstek bağımlılıkları: oturumdaki kullanıcı.

- current_user: giriş gerektiren uç noktalar; oturum yoksa 401.
- optional_user: herkese açık uç noktalar; girişli kullanıcı varsa döner.

CSRF: oturum çerezi SameSite=Lax; ayrıca çerezli ve durum değiştiren (POST/PUT/PATCH/DELETE) isteklerde
X-Requested-With başlığı zorunludur (csrf_guard, app/main.py). Başka bir siteden gönderilen form bu başlığı
ekleyemez; fetch ile eklemeye çalışırsa tarayıcı CORS ön kontrolü yapar ve izin verilen tek köken frontend'dir.
"""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.services import auth

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = "x-requested-with"


def session_token(request: Request) -> str | None:
    return request.cookies.get(settings.cookie_name)


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    return auth.user_for_token(db, session_token(request))


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(401, "Bu işlem için giriş yapmalısınız.")
    return user


def csrf_violation(request: Request) -> bool:
    return (request.method in UNSAFE and request.url.path.startswith("/api/")
            and settings.cookie_name in request.cookies and not request.headers.get(CSRF_HEADER))
