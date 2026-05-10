from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import Status


class Lieferschein(Base):
    __tablename__ = "lieferscheine"

    id: Mapped[int] = mapped_column(primary_key=True)
    dateiname: Mapped[str]
    dateipfad: Mapped[str]
    format_typ: Mapped[Optional[str]] = mapped_column(default=None)
    ocr_text_roh: Mapped[Optional[str]] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default=Status.pending)
    erstellt_am: Mapped[datetime]
    bearbeitet_am: Mapped[Optional[datetime]] = mapped_column(default=None)

    positionen: Mapped[list["Position"]] = relationship(
        back_populates="lieferschein", cascade="all, delete-orphan"
    )


class Position(Base):
    __tablename__ = "positionen"

    id: Mapped[int] = mapped_column(primary_key=True)
    lieferschein_id: Mapped[int] = mapped_column(ForeignKey("lieferscheine.id"))
    produktname: Mapped[str]
    menge: Mapped[float]
    einheit: Mapped[str]
    konfidenz: Mapped[Optional[float]] = mapped_column(default=None)
    manuell_korrigiert: Mapped[bool] = mapped_column(default=False)

    lieferschein: Mapped["Lieferschein"] = relationship(back_populates="positionen")


class Lagerbestand(Base):
    __tablename__ = "lagerbestand"

    id: Mapped[int] = mapped_column(primary_key=True)
    produktname: Mapped[str] = mapped_column(unique=True)
    bestand: Mapped[float] = mapped_column(default=0.0)
    einheit: Mapped[str]
    mindestbestand: Mapped[float] = mapped_column(default=0.0)
    zuletzt_geliefert: Mapped[Optional[datetime]] = mapped_column(default=None)
