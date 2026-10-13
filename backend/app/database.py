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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
