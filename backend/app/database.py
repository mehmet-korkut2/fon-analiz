import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


log = logging.getLogger(__name__)


def init_db(bind=None):
    """Tabloları oluşturur ve mevcut tablolara sonradan eklenen boş bırakılabilir sütunları ekler.

    create_all var olan tabloya sütun eklemez. Alembic'e geçene kadar yeni metrik sütunları
    (ör. ret_3y) bu şekilde eklenir; sadece NULL olabilen sütunlar desteklenir.
    """
    bind = bind or engine
    _migrate_before(bind)
    Base.metadata.create_all(bind=bind)
    insp = inspect(bind)
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing or not col.nullable:
                    continue
                ddl = col.type.compile(dialect=bind.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl}'))
                log.info("Sütun eklendi: %s.%s", table.name, col.name)
        # sonradan eklenen user_id sütunlarının indeksleri (yeni kurulumda create_all zaten oluşturur)
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_sanal_portfoy_user_id ON sanal_portfoy (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sanal_emirler_user_id ON sanal_emirler (user_id)"))


def _migrate_before(bind) -> None:
    """Kullanıcı girişiyle değişen tablolar. sanal_degerler'in birincil anahtarı (tarih) -> (kullanıcı, tarih)
    oldu; SQLite birincil anahtarı değiştirmeye izin vermez. Bu tablo emirlerden türetilir (her emirden ve gece
    güncellemesinden sonra yeniden hesaplanır), bu yüzden eski hâli kaldırılır ve create_all yeniden kurar."""
    insp = inspect(bind)
    if "sanal_degerler" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("sanal_degerler")}
        if "user_id" not in cols:
            with bind.begin() as conn:
                conn.execute(text("DROP TABLE sanal_degerler"))
            log.info("sanal_degerler kullanıcıya özel olarak yeniden kuruldu (değerler emirlerden yeniden hesaplanır)")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
