"""Robuste OCR-Pipeline für Lieferscheine (Fotos und Scans)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import cv2
import fitz
import numpy as np
import pytesseract
from PIL import Image

# ─── Konfiguration ─────────────────────────────────────────────────────────

_TESS_LANG = "deu"
_TESS_LINE = "--psm 7 --oem 1"   # Einzelzeile (optimal für isolierte Tabellenzeilen)
_TESS_BLOCK = "--psm 6 --oem 1"  # Gleichförmiger Textblock (Fallback)

# Bekannte OCR-Fehllesungen: OCR-Output → korrekter Wert
_UNIT_FIXES: dict[str, str] = {
    "XRT": "KRT",
    "XRTN": "KRTN",
    "D0S": "DOS",
    "5TK": "STK",
    "5TU": "STU",
}

# ─── Laden ─────────────────────────────────────────────────────────────────


def pdf_to_images(pdf_path: str) -> list[Image.Image]:
    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=300)  # type: ignore[attr-defined]
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images


def file_to_images(file_path: str) -> list[Image.Image]:
    if Path(file_path).suffix.lower() == ".pdf":
        return pdf_to_images(file_path)
    return [Image.open(file_path).convert("RGB")]


# ─── Perspektivkorrektur ───────────────────────────────────────────────────


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Sortiert 4 Punkte: oben-links, oben-rechts, unten-rechts, unten-links."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]    # kleinste Summe = oben-links
    rect[2] = pts[np.argmax(s)]    # größte Summe = unten-rechts
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)] # kleinste Differenz = oben-rechts
    rect[3] = pts[np.argmax(diff)] # größte Differenz = unten-links
    return rect


def _four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    rect = _order_points(pts)
    tl, tr, br, bl = rect
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype="float32",
    )
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (width, height))


def detect_and_warp(img: np.ndarray) -> np.ndarray:
    """Größte viereckige Kontur (= Papier) finden und perspektivisch entzerren.

    Canny-Kanten + Kontur-Approximation suchen nach einem Rechteck das
    mindestens 30% der Bildfläche bedeckt. Wird keines gefunden, wird das
    Originalbild zurückgegeben (Fallback für schlechte Aufnahmen).
    """
    h, w = img.shape[:2]
    min_area = h * w * 0.30

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 75, 200)

    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    for c in contours:
        if cv2.contourArea(c) < min_area:
            break
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            return _four_point_transform(img, approx.reshape(4, 2))

    return img


# ─── Vorverarbeitung ───────────────────────────────────────────────────────


def _remove_shadows(gray: np.ndarray) -> np.ndarray:
    """Schattenkorrektur: normalisiert ungleichmäßige Beleuchtung.

    Morphologische Dilatation mit großem Kernel erzeugt ein Hintergrundbild
    das Textelemente ignoriert. Division durch diesen Hintergrund
    normalisiert die lokale Helligkeit über das gesamte Bild.
    """
    h, w = gray.shape
    # Kernel ~2% der kürzeren Bildkante; `| 1` stellt ungerade Größe sicher
    k = max(25, min(h, w) // 50) | 1
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    bg = cv2.morphologyEx(gray, cv2.MORPH_DILATE, kernel)
    bg = cv2.GaussianBlur(bg, (21, 21), 0)
    normalized = cv2.divide(gray.astype(np.float32), bg.astype(np.float32), scale=255)
    return np.clip(normalized, 0, 255).astype(np.uint8)


def preprocess(img: np.ndarray) -> np.ndarray:
    """Vollständige Vorverarbeitungs-Pipeline für Lieferschein-Fotos.

    Adaptives Thresholding statt Otsu: berücksichtigt lokale Helligkeitsunterschiede
    innerhalb des Bildes. Besser für Fotos mit Schatten, Falten oder grauem Tischhintergrund.
    blockSize=31 definiert die lokale Nachbarschaft; C=10 subtrahiert einen Konstantwert
    um schwache Grauflächen zu eliminieren.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray = _remove_shadows(gray)
    denoised = cv2.fastNlMeansDenoising(gray, h=7)
    # blockSize skaliert mit der Bildgröße (~2% der kürzeren Kante, muss ungerade sein)
    h, w = denoised.shape
    block = max(11, min(h, w) // 50) | 1
    thresh = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=block,
        C=10,
    )
    return thresh


# ─── Zeilenextraktion ──────────────────────────────────────────────────────


def _extract_rows(
    thresh: np.ndarray, padding: int = 3, min_height: int = 12
) -> list[np.ndarray]:
    """Text-Zeilen per horizontalem Projektionsprofil extrahieren.

    Zählt schwarze Pixel (Text = 0 nach THRESH_BINARY) pro Bildzeile.
    Zusammenhängende Bereiche mit ausreichend Text werden als Zeilen ausgeschnitten.
    Jede Zeile wird mit `padding` Pixeln oben und unten ergänzt damit Tesseract
    keine abgeschnittenen Buchstaben erhält.
    """
    h, w = thresh.shape
    density = (thresh == 0).sum(axis=1).astype(np.float32)
    min_density = max(w * 0.005, 2)  # Mindestdichte: 0.5% der Bildbreite

    rows: list[np.ndarray] = []
    start: Optional[int] = None

    for i, d in enumerate(density):
        if d > min_density and start is None:
            start = i
        elif d <= min_density and start is not None:
            if i - start >= min_height:
                y0 = max(0, start - padding)
                y1 = min(h, i + padding)
                rows.append(thresh[y0:y1, :])
            start = None

    if start is not None and h - start >= min_height:
        rows.append(thresh[max(0, start - padding) : h, :])

    return rows


# ─── OCR-Fehlerkorrektur ───────────────────────────────────────────────────


def _correct_ocr_errors(text: str) -> str:
    """Bekannte OCR-Fehllesungen für Einheiten und Ziffernfolgen korrigieren."""
    for wrong, correct in _UNIT_FIXES.items():
        text = re.sub(rf"\b{re.escape(wrong)}\b", correct, text, flags=re.IGNORECASE)
    # Buchstabe O/o zwischen Ziffern ist fast immer eine 0
    text = re.sub(r"(?<=\d)[oO](?=\d)", "0", text)
    # Buchstabe l/I zwischen Ziffern ist fast immer eine 1
    text = re.sub(r"(?<=\d)[lI](?=\d)", "1", text)
    return text


# ─── OCR ───────────────────────────────────────────────────────────────────


def _run_tesseract(arr: np.ndarray, config: str) -> tuple[str, float]:
    data = pytesseract.image_to_data(
        arr, lang=_TESS_LANG, config=config, output_type=pytesseract.Output.DICT
    )
    confs = [c for c in data["conf"] if c > 0]
    avg_conf = (sum(confs) / len(confs) / 100) if confs else 0.0

    # Wörter nach (block, para, line) gruppieren → Zeilenstruktur bleibt erhalten
    lines: dict[tuple[int, int, int], list[str]] = {}
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)

    return "\n".join(" ".join(ws) for ws in lines.values()), avg_conf


def ocr_page(pil_img: Image.Image) -> tuple[str, float]:
    """Robuste Einzelseiten-Pipeline.

    1. Perspektivkorrektur (Dokumenterkennung via Konturen)
    2. Vorverarbeitung (Shadow removal + adaptives Thresholding)
    3. Zeilenweises OCR mit PSM 7 wenn >= 3 Zeilen erkannt
    4. Fallback: Ganzseitiges OCR mit PSM 6
    5. Fehlerkorrektur auf bekannte OCR-Muster
    """
    arr = np.array(pil_img)
    warped = detect_and_warp(arr)
    thresh = preprocess(warped)
    rows = _extract_rows(thresh)

    if len(rows) >= 3:
        line_results = [_run_tesseract(r, _TESS_LINE) for r in rows]
        lines = [t for t, _ in line_results if t.strip()]
        confs = [c for _, c in line_results if c > 0]
        text = "\n".join(lines)
        avg_conf = sum(confs) / len(confs) if confs else 0.0
    else:
        text, avg_conf = _run_tesseract(thresh, _TESS_BLOCK)

    return _correct_ocr_errors(text), avg_conf


def ocr_file(file_path: str) -> tuple[str, float]:
    """OCR über alle Seiten/Frames einer Datei, gibt (text, avg_konfidenz) zurück."""
    images = file_to_images(file_path)
    results = [ocr_page(img) for img in images]
    texts = [t for t, _ in results]
    confs = [c for _, c in results]
    return "\n".join(texts), sum(confs) / len(confs) if confs else 0.0
