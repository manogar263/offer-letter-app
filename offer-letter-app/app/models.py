from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Company(Base):
    """Branding and signatory details. Filled once by the company."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    tagline: Mapped[str] = mapped_column(String(200), default="")
    website: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    logo_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    founder_name: Mapped[str] = mapped_column(String(120))
    founder_title: Mapped[str] = mapped_column(String(120), default="Founder")
    signature_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    letters: Mapped[list["OfferLetter"]] = relationship(back_populates="company")


class OfferLetter(Base):
    """One offer letter. Filled by the company for each candidate."""

    __tablename__ = "offer_letters"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    candidate_name: Mapped[str] = mapped_column(String(120))
    candidate_email: Mapped[str] = mapped_column(String(254), default="")
    candidate_address: Mapped[str] = mapped_column(String(200), default="")
    position: Mapped[str] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date)
    employment_type: Mapped[str] = mapped_column(String(30))
    work_location: Mapped[str] = mapped_column(String(200))
    body_text: Mapped[str] = mapped_column(Text, default="")
    letter_date: Mapped[date] = mapped_column(Date, default=date.today)
    status: Mapped[str] = mapped_column(String(20), default="Issued")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped[Company] = relationship(back_populates="letters")
