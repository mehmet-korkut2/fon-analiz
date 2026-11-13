"""Kullanıcıya özel veriler (giriş gerekir): kaydedilmiş risk profili ve favori fonlar.
Sanal portföy: app/routers/sanal.py."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import current_user
from app.ml.horizons import recent_hits
from app.models import Favorite, Fund, RiskProfile, SanalAyar, User
from app.routers.funds import fund_out, stale_cutoff
from app.routers.risk import evaluate_profile
from app.schemas import FavoriteForecast, FavoriteOut, FavoritePosition, ProfileIn, ProfileOut, SavedProfileOut
from app.services import sanal_portfoy as S
from app.services.fund_status import STATUS_ACTIVE

router = APIRouter(tags=["hesap"])


# --- risk profili ---------------------------------------------------------------------------------

def _saved(p: RiskProfile) -> SavedProfileOut:
    return SavedProfileOut(answers=p.answers, qualified=bool(p.qualified), result=ProfileOut(**p.result),
                           saved_at=p.created_at or datetime.now())


@router.get("/profilim", response_model=SavedProfileOut | None)
def my_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Kullanıcının en son kaydettiği risk profili (yoksa null)."""
    p = db.scalars(select(RiskProfile).where(RiskProfile.user_id == user.id, RiskProfile.result.is_not(None))
                   .order_by(RiskProfile.id.desc()).limit(1)).first()
    return _saved(p) if p else None


@router.post("/profilim", response_model=SavedProfileOut)
def save_profile(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Anket cevaplarından profil hesaplanır ve kaydedilir; geçmiş tutulur, en sonuncusu geçerlidir."""
    out = evaluate_profile(body)
    p = RiskProfile(user_id=user.id, score=out.score, profile=out.profile, answers=body.answers,
                    qualified=body.qualified, result=out.model_dump(mode="json"), created_at=datetime.now())
    db.add(p)
    db.commit()
    return _saved(p)


@router.delete("/profilim", status_code=204)
def clear_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(RiskProfile).where(RiskProfile.user_id == user.id))
    db.commit()


# --- favoriler ------------------------------------------------------------------------------------

def _positions(db: Session, user: User) -> dict[str, FavoritePosition]:
    """Kullanıcının sanal portföyündeki açık pozisyonlar (portföyü yoksa boş; burada oluşturulmaz)."""
    if db.scalar(select(SanalAyar.id).where(SanalAyar.user_id == user.id)) is None:
        return {}
    out = {}
    for code, p in S.state(db, user.id).positions.items():
        if p.units <= 0:
            continue
        s = S.price_series(db, code)
        value = p.units * float(s.iloc[-1]) if len(s) else 0.0
        out[code] = FavoritePosition(units=p.units, value=round(value, 2), pnl=round(value - p.cost, 2),
                                     pnl_pct=value / p.cost - 1 if p.cost else None)
    return out


def _warning(f) -> str | None:
    if (f.status or STATUS_ACTIVE) != STATUS_ACTIVE:
        return f.status_note or "SPK kararıyla işleme kapatıldı."
    if f.is_stale:
        return f"Verisi {f.price_date:%d.%m.%Y} tarihinden beri güncellenmiyor." if f.price_date else "Verisi güncellenmiyor."
    return None


@router.get("/favoriler", response_model=list[FavoriteOut])
def favorites(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Favori fonlar (en yeni eklenen başta): fon bilgisi ve metrikler, kapatılmış/eski verili uyarısı, son
    tahminlerin aralıkta kalma özeti ve kullanıcının sanal portföyündeki pozisyon."""
    rows = db.scalars(select(Favorite).where(Favorite.user_id == user.id).order_by(Favorite.id.desc())).all()
    codes = [r.fund_code for r in rows]
    funds = {f.code: f for f in db.scalars(select(Fund).options(joinedload(Fund.metrics))
                                           .where(Fund.code.in_(codes))).unique()}
    cutoff = stale_cutoff(db)
    hits = recent_hits(db, codes)
    pos = _positions(db, user)
    out = []
    for r in rows:
        if r.fund_code not in funds:
            continue
        f = fund_out(funds[r.fund_code], cutoff)
        h = hits.get(r.fund_code)
        out.append(FavoriteOut(**f.model_dump(), added_at=r.created_at, warning=_warning(f),
                               forecast=FavoriteForecast(**h) if h else None, position=pos.get(r.fund_code)))
    return out


@router.post("/favoriler/{code}", status_code=204)
def add_favorite(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    code = code.upper()
    if db.get(Fund, code) is None:
        raise HTTPException(404, f"{code} kodlu fon bulunamadı.")
    exists = db.scalar(select(Favorite.id).where(Favorite.user_id == user.id, Favorite.fund_code == code))
    if exists is None:
        db.add(Favorite(user_id=user.id, fund_code=code))
        db.commit()


@router.delete("/favoriler/{code}", status_code=204)
def remove_favorite(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(Favorite).where(Favorite.user_id == user.id, Favorite.fund_code == code.upper()))
    db.commit()
