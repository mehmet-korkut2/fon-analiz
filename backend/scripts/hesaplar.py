"""Hesapları listeler: yalnızca e-posta, ad ve oluşturma tarihi. Şifre bilgisi (özet dahil) hiçbir zaman gösterilmez.

    python -m scripts.hesaplar

Şifresini unutan kullanıcı için: python -m scripts.sifre_sifirla --eposta <adres>
"""
import sys

from app.database import SessionLocal, init_db
from app.services import auth


def main() -> int:
    init_db()
    with SessionLocal() as db:
        rows = auth.list_accounts(db)
    if not rows:
        print("Kayıtlı hesap yok.")
        return 0
    w = max(len("E-posta"), *(len(r["email"]) for r in rows))
    n = max(len("Ad"), *(len(r["name"] or "") for r in rows))
    print(f"{'E-posta':<{w}}  {'Ad':<{n}}  Oluşturma")
    for r in rows:
        when = r["created_at"].strftime("%d.%m.%Y %H:%M") if r["created_at"] else "-"
        print(f"{r['email']:<{w}}  {(r['name'] or '-'):<{n}}  {when}")
    print(f"\n{len(rows)} hesap.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
