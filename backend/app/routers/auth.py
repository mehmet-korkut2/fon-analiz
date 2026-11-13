"""Kayıt, giriş, çıkış, şifre değiştirme, hesap silme. Mantık: app/services/auth.py"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import current_user, optional_user, session_token
from app.models import User
from app.schemas import AccountDeleteIn, AuthOut, LoginIn, MeOut, PasswordChangeIn, RegisterIn, UserOut
from app.services import auth as A

router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(u: User) -> UserOut:
    return UserOut(id=u.id, email=u.email, name=u.full_name, created_at=u.created_at)


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.cookie_name, token, max_age=settings.session_days * 86400, httponly=True,
        samesite="lax", secure=settings.cookie_secure, path="/api",
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(settings.cookie_name, path="/api", httponly=True, samesite="lax", secure=settings.cookie_secure)


def _fail(e: A.AuthHata):
    headers = {"Retry-After": str(e.retry_after)} if e.retry_after else None
    raise HTTPException(e.status, str(e), headers=headers) from e


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/ben", response_model=MeOut)
def me(user: User | None = Depends(optional_user)):
    """Oturumdaki kullanıcı; giriş yapılmamışsa {"user": null} (401 değil)."""
    return MeOut(user=user_out(user) if user else None)


@router.post("/kayit", response_model=AuthOut, status_code=201)
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        r = A.register(db, body.email, body.password, body.name)
    except A.AuthHata as e:
        _fail(e)
    A.end_session(db, session_token(request))  # varsa önceki oturum kapanır
    _set_cookie(response, A.create_session(db, r.user))
    return AuthOut(user=user_out(r.user), migrated_portfolio=r.migrated_portfolio)


@router.post("/giris", response_model=AuthOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        user = A.login(db, body.email, body.password, client_ip(request))
    except A.AuthHata as e:
        _fail(e)
    A.end_session(db, session_token(request))  # oturum sabitlemeye karşı: girişte her zaman yeni belirteç
    _set_cookie(response, A.create_session(db, user))
    return AuthOut(user=user_out(user))


@router.post("/cikis", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)):
    A.end_session(db, session_token(request))
    r = Response(status_code=204)
    _clear_cookie(r)
    return r


@router.post("/sifre", response_model=AuthOut)
def change_password(body: PasswordChangeIn, request: Request, response: Response,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Mevcut şifre doğrulanır; diğer bütün oturumlar kapanır, bu oturum yeni belirteçle sürer."""
    old = session_token(request)
    try:
        A.change_password(db, user, body.current_password, body.new_password, keep_token=old)
    except A.AuthHata as e:
        _fail(e)
    A.end_session(db, old)
    _set_cookie(response, A.create_session(db, user))
    return AuthOut(user=user_out(user))


@router.delete("/hesap", status_code=204)
def delete_account(body: AccountDeleteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Hesap ve bütün kişisel veriler (risk profili, sanal portföy, favoriler, oturumlar) silinir."""
    try:
        A.delete_account(db, user, body.password)
    except A.AuthHata as e:
        _fail(e)
    r = Response(status_code=204)
    _clear_cookie(r)
    return r
