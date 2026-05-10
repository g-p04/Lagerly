import re

from app.formats.backring import parse as _parse_backring
from app.formats.iceflow import parse as _parse_iceflow

_SEP = re.compile(r'^\s*\*{3,}\s*$', re.MULTILINE)


def detect_format(text: str) -> str:
    # Primär: explizite ***-Trennzeile; Fallback: Firmenname im OCR-Text
    if _SEP.search(text) or 'BACKRING' in text.upper():
        return 'Backring'
    return 'IceFlow'


def parse_auto(text: str) -> tuple[str, list[dict]]:
    fmt = detect_format(text)
    if fmt == 'Backring':
        return fmt, _parse_backring(text)
    return fmt, _parse_iceflow(text)
