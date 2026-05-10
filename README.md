# Lagerly

Warehouse management tool that digitizes paper delivery notes via OCR. Upload a photo or PDF of a delivery note, review the automatically extracted line items, approve or correct them, and watch the inventory update in real time.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square)
![Tests](https://img.shields.io/badge/Tests-46%20passing-brightgreen?style=flat-square)

---

## Features

- **OCR pipeline** — perspective correction, shadow removal, adaptive thresholding, per-row Tesseract (PSM 7) with full-page fallback (PSM 6)
- **Two delivery note formats** — IceFlow and Backring, auto-detected from OCR output
- **Review workflow** — inspect and correct extracted line items before approving
- **Inventory management** — stock levels update on approval; low-stock warnings for items below minimum threshold
- **REST API** — 11 endpoints covering upload, CRUD on line items, approval/rejection, and inventory edits
- **46 tests** — parser unit tests and full API integration tests (pytest + httpx, in-memory SQLite)

## Tech Stack

| Layer     | Technology                            |
|-----------|---------------------------------------|
| Backend   | FastAPI, SQLAlchemy 2.0, Pydantic v2  |
| Database  | SQLite                                |
| OCR       | Tesseract, OpenCV, PyMuPDF            |
| Frontend  | Vanilla HTML / CSS / JS (single file) |
| Tests     | pytest, httpx                         |

## Architecture

```
app/
├── main.py          # API endpoints (FastAPI)
├── models.py        # ORM models (SQLAlchemy 2.0 Mapped-style)
├── schmas.py        # Request/response schemas (Pydantic v2)
├── database.py      # Engine, session, Base
├── ocr.py           # 7-stage OCR pipeline
├── parser.py        # Format dispatcher
└── formats/
    ├── iceflow.py   # IceFlow regex parser
    └── backring.py  # Backring regex parser
static/
└── index.html       # Single-page frontend
tests/
├── conftest.py      # pytest fixtures (TestClient, in-memory DB)
├── test_parsers.py  # Parser unit tests (22)
└── test_api.py      # API integration tests (24)
```

## OCR Pipeline

1. **Perspective correction** — Canny edge detection + contour approximation finds the document rectangle and applies a four-point transform
2. **Shadow removal** — morphological dilation builds a background model; dividing by it normalises uneven lighting
3. **Adaptive thresholding** — `ADAPTIVE_THRESH_GAUSSIAN_C` handles local brightness variation across the image
4. **Row extraction** — horizontal projection profile segments table rows
5. **Per-row OCR** — Tesseract PSM 7 on each row; PSM 6 full-page fallback when fewer than 3 rows are found
6. **Error correction** — regex rules fix common Tesseract misreads (`XRT→KRT`, `O between digits→0`, etc.)

## API

### Delivery Notes

| Method   | Path                                      | Description                        |
|----------|-------------------------------------------|------------------------------------|
| `POST`   | `/upload`                                 | Upload file and run OCR            |
| `GET`    | `/lieferscheine`                          | List all delivery notes            |
| `GET`    | `/lieferscheine/{id}`                     | Get single delivery note           |
| `PUT`    | `/lieferscheine/{id}/positionen`          | Update line items                  |
| `POST`   | `/lieferscheine/{id}/positionen`          | Add line item manually             |
| `DELETE` | `/lieferscheine/{id}/positionen/{pos_id}` | Delete line item                   |
| `POST`   | `/lieferscheine/{id}/approve`             | Approve and update inventory       |
| `POST`   | `/lieferscheine/{id}/reject`              | Reject                             |
| `DELETE` | `/lieferscheine/{id}`                     | Delete delivery note               |

### Inventory

| Method | Path             | Description                       |
|--------|------------------|-----------------------------------|
| `GET`  | `/lager`         | Get full inventory                |
| `GET`  | `/lager/niedrig` | Get items below minimum stock     |
| `PUT`  | `/lager/{id}`    | Update stock level or unit        |

## Status Workflow

```
pending → review → approved
                 → rejected
```

| Status     | Meaning                                      |
|------------|----------------------------------------------|
| `pending`  | Upload failed or OCR returned no results     |
| `review`   | OCR succeeded, awaiting manual review        |
| `approved` | Approved, inventory updated                  |
| `rejected` | Rejected                                     |

## Setup

**Requirements:** Python 3.11+, [Tesseract](https://github.com/tesseract-ocr/tesseract) with German language data (`tesseract-ocr-deu`)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000`.

**Run tests:**

```bash
pytest tests/ -v
```
