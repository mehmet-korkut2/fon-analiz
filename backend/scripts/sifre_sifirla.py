"""Bir hesabın şifresini bilgisayardan sıfırlar (e-posta altyapısı olmadığı için şifresini unutan kullanıcı içindir).

    python -m scripts.sifre_sifirla --eposta ali@ornek.com

Yeni şifre ekrana yazılmadan iki kez sorulur (getpass); komut satırında, ortam değişkeninde ya da günlükte yer
almaz. Şifre kuralı (8-128 karakter) uygulanır. Kullanıcının bütün açık oturumları kapatılır (başka cihazlarda
giriş yapmış olsa da yeniden giriş yapması gerekir) ve hatalı giriş beklemesi sıfırlanır. Mevcut şifre
sorulmaz: komutu yalnızca bu bilgisayardaki veritabanına erişimi olan kişi çalıştırabilir.
Hesapları görmek için: python -m scripts.hesaplar
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import User
from app.services import auth


def main(argv: list[str] | None = None, ask=getpass.getpass) -> int:
    ap = argparse.ArgumentParser(description="Hesap şifresini sıfırla (yerel)")
    ap.add_argument("--eposta", required=True, help="Hesabın e-posta adresi")
    args = ap.parse_args(argv)

    init_db()
    email = auth.normalize_email(args.eposta)
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == email)) is None:
            print(f"Hata: {email} adresiyle kayıtlı hesap yok. Hesaplar: python -m scripts.hesaplar", file=sys.stderr)
            return 1
        try:
            new = ask(f"{email} için yeni şifre (en az {auth.PASSWORD_MIN} karakter): ")
            again = ask("Yeni şifre (tekrar): ")
        except (KeyboardInterrupt, EOFError):
            print("\nVazgeçildi; şifre değişmedi.", file=sys.stderr)
            return 1
        if new != again:
            print("Hata: şifreler aynı değil; şifre değişmedi.", file=sys.stderr)
            return 1
        try:
            _, closed = auth.reset_password(db, email, new)
        except auth.AuthHata as e:
            print(f"Hata: {e} Şifre değişmedi.", file=sys.stderr)
            return 1
    print(f"Şifre değiştirildi: {email}. Kapatılan oturum: {closed}. Kullanıcı yeni şifreyle giriş yapabilir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
