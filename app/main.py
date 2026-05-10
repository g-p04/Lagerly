import os
import shutil
from datetime import datetime

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import schmas
from app.database import get_db, init_db
from app.enums import Status
from app.models import Lagerbestand, Lieferschein, Position
from app.ocr import ocr_file
from app.parser import parse_positionen

app = FastAPI(title="Lagerly")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
def startup():
    init_db()


@app.post("/upload", response_model=schmas.LieferscheinListItem, status_code=201)
def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = file.filename or "upload"
    dateipfad = os.path.join(UPLOAD_DIR, filename)
    with open(dateipfad, "wb") as f:
        shutil.copyfileobj(file.file, f)

    lieferschein = Lieferschein(
        dateiname=filename,
        dateipfad=dateipfad,
        status=Status.pending,
        erstellt_am=datetime.utcnow(),
    )
    db.add(lieferschein)
    db.flush()

    try:
        ocr_text, _ = ocr_file(dateipfad)
        lieferschein.ocr_text_roh = ocr_text
        fmt, positionen = parse_positionen(ocr_text)
        lieferschein.format_typ = fmt
        for pos_data in positionen:
            db.add(Position(lieferschein_id=lieferschein.id, **pos_data))
        lieferschein.status = Status.review
    except Exception:
        pass  # OCR fehlgeschlagen, Status bleibt pending

    db.commit()
    db.refresh(lieferschein)
    return lieferschein


@app.get("/lieferscheine", response_model=list[schmas.LieferscheinListItem])
def list_lieferscheine(db: Session = Depends(get_db)):
    return db.query(Lieferschein).all()


@app.get("/lieferscheine/{id}", response_model=schmas.LieferscheinRead)
def get_lieferschein(id: int, db: Session = Depends(get_db)):
    obj = db.get(Lieferschein, id)
    if not obj:
        raise HTTPException(404, "Lieferschein nicht gefunden")
    return obj


@app.put("/lieferscheine/{id}/positionen", response_model=schmas.LieferscheinRead)
def update_positionen(id: int, updates: list[schmas.PositionUpdate], db: Session = Depends(get_db)):
    lieferschein = db.get(Lieferschein, id)
    if not lieferschein:
        raise HTTPException(404, "Lieferschein nicht gefunden")
    for update in updates:
        pos = db.get(Position, update.id)
        if pos and pos.lieferschein_id == id:
            for field, value in update.model_dump(exclude_none=True, exclude={"id"}).items():
                setattr(pos, field, value)
            pos.manuell_korrigiert = True
    lieferschein.bearbeitet_am = datetime.utcnow()
    db.commit()
    db.refresh(lieferschein)
    return lieferschein


@app.post("/lieferscheine/{id}/approve", response_model=schmas.LieferscheinRead)
def approve_lieferschein(id: int, db: Session = Depends(get_db)):
    lieferschein = db.get(Lieferschein, id)
    if not lieferschein:
        raise HTTPException(404, "Lieferschein nicht gefunden")
    if lieferschein.status == Status.approved:
        raise HTTPException(400, "Lieferschein bereits genehmigt")
    for pos in lieferschein.positionen:
        lager = db.query(Lagerbestand).filter_by(produktname=pos.produktname).first()
        if lager:
            lager.bestand += pos.menge
            lager.zuletzt_geliefert = datetime.utcnow()
        else:
            db.add(Lagerbestand(
                produktname=pos.produktname,
                bestand=pos.menge,
                einheit=pos.einheit,
                zuletzt_geliefert=datetime.utcnow(),
            ))
    lieferschein.status = Status.approved
    lieferschein.bearbeitet_am = datetime.utcnow()
    db.commit()
    db.refresh(lieferschein)
    return lieferschein


@app.post("/lieferscheine/{id}/reject", response_model=schmas.LieferscheinRead)
def reject_lieferschein(id: int, db: Session = Depends(get_db)):
    lieferschein = db.get(Lieferschein, id)
    if not lieferschein:
        raise HTTPException(404, "Lieferschein nicht gefunden")
    if lieferschein.status == Status.approved:
        raise HTTPException(400, "Genehmigte Lieferscheine können nicht abgelehnt werden")
    lieferschein.status = Status.rejected
    lieferschein.bearbeitet_am = datetime.utcnow()
    db.commit()
    db.refresh(lieferschein)
    return lieferschein


@app.post("/lieferscheine/{id}/positionen", response_model=schmas.LieferscheinRead, status_code=201)
def add_position(id: int, pos: schmas.PositionCreate, db: Session = Depends(get_db)):
    lieferschein = db.get(Lieferschein, id)
    if not lieferschein:
        raise HTTPException(404, "Lieferschein nicht gefunden")
    if lieferschein.status == Status.approved:
        raise HTTPException(400, "Genehmigte Lieferscheine können nicht bearbeitet werden")
    db.add(Position(lieferschein_id=id, **pos.model_dump()))
    lieferschein.bearbeitet_am = datetime.utcnow()
    db.commit()
    db.refresh(lieferschein)
    return lieferschein


@app.delete("/lieferscheine/{id}", status_code=204)
def delete_lieferschein(id: int, db: Session = Depends(get_db)):
    lieferschein = db.get(Lieferschein, id)
    if not lieferschein:
        raise HTTPException(404, "Lieferschein nicht gefunden")
    db.delete(lieferschein)
    db.commit()


@app.delete("/lieferscheine/{id}/positionen/{pos_id}", status_code=204)
def delete_position(id: int, pos_id: int, db: Session = Depends(get_db)):
    pos = db.get(Position, pos_id)
    if not pos or pos.lieferschein_id != id:
        raise HTTPException(404, "Position nicht gefunden")
    db.delete(pos)
    db.commit()


@app.put("/lager/{id}", response_model=schmas.LagerbestandRead)
def update_lager(id: int, update: schmas.LagerbestandUpdate, db: Session = Depends(get_db)):
    lager = db.get(Lagerbestand, id)
    if not lager:
        raise HTTPException(404, "Artikel nicht gefunden")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(lager, field, value)
    db.commit()
    db.refresh(lager)
    return lager


@app.get("/lager", response_model=list[schmas.LagerbestandRead])
def get_lager(db: Session = Depends(get_db)):
    return db.query(Lagerbestand).all()


@app.get("/lager/niedrig", response_model=list[schmas.LagerbestandRead])
def get_lager_niedrig(db: Session = Depends(get_db)):
    return db.query(Lagerbestand).filter(
        Lagerbestand.bestand <= Lagerbestand.mindestbestand
    ).all()


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse("static/index.html")
