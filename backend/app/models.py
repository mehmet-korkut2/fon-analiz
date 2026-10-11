from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Fund(Base):
    __tablename__ = "funds"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100))
    company: Mapped[str | None] = mapped_column(String(255))
    risk_level: Mapped[int | None]

    prices: Mapped[list["Price"]] = relationship(back_populates="fund")


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (UniqueConstraint("fund_code", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_code: Mapped[str] = mapped_column(ForeignKey("funds.code"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    price: Mapped[float] = mapped_column(Float)

    fund: Mapped[Fund] = relationship(back_populates="prices")
