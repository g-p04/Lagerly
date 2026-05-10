from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PositionRead(BaseModel):
    id: int
    lieferschein_id: int
    produktname: str
    menge: float
    einheit: str
    konfidenz: Optional[float] = None
    manuell_korrigiert: bool

    model_config = ConfigDict(from_attributes=True)


class PositionUpdate(BaseModel):
    id: int
    produktname: Optional[str] = None
    menge: Optional[float] = None
    einheit: Optional[str] = None


class PositionCreate(BaseModel):
    produktname: str
    menge: float
    einheit: str


class LieferscheinListItem(BaseModel):
    id: int
    dateiname: str
    format_typ: Optional[str] = None
    status: str
    erstellt_am: datetime

    model_config = ConfigDict(from_attributes=True)


class LieferscheinRead(BaseModel):
    id: int
    dateiname: str
    dateipfad: str
    format_typ: Optional[str] = None
    ocr_text_roh: Optional[str] = None
    status: str
    erstellt_am: datetime
    bearbeitet_am: Optional[datetime] = None
    positionen: list[PositionRead] = []

    model_config = ConfigDict(from_attributes=True)


class LagerbestandUpdate(BaseModel):
    bestand: Optional[float] = None
    einheit: Optional[str] = None
    mindestbestand: Optional[float] = None


class LagerbestandRead(BaseModel):
    id: int
    produktname: str
    bestand: float
    einheit: str
    mindestbestand: float
    zuletzt_geliefert: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
