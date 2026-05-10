"""
IceFlow-Lieferschein-Format.

Struktur pro Zeile:
  Artikel-Nr.  Bezeichnung  Menge  Einheit

Beispiel:
  12345  Milch homogenisiert  3.5  L
  10023  Butter 82%           250  g
"""
import re

_EINHEITEN = (
    r'kg|g|l|ml|liter'
    r'|fl|fla|flasche'
    r'|stueck|stue|stk|st|stück'
    r'|pack|pck|pac|karton|krt'
    r'|dose|dos|btl|beutel'
)

# Keine ^ Anker: Artikelnummer kann nach OCR-Rauschen auftreten.
# (?<!\d)/(?!\d) verhindert Matches innerhalb größerer Zahlen.
_PATTERN = re.compile(
    r'(?<!\d)(?P<artnr>\d{3,8})(?!\d)'
    r'\s+(?P<name>[A-Za-zäöüÄÖÜß][^\n]*?)'
    r'\s+(?P<menge>\d+[.,]\d+|\d+)'
    r'\s+(?P<einheit>' + _EINHEITEN + r')\b',
    re.IGNORECASE | re.MULTILINE,
)


def parse(text: str) -> list[dict]:
    results = []
    for m in _PATTERN.finditer(text):
        name = m.group('name').strip()
        # Trailing Zahlen/Sonderzeichen entfernen (OCR-Artefakte)
        name = re.sub(r'[\d.,\-]+$', '', name).strip()
        if len(name) < 2:
            continue
        results.append({
            'produktname': name,
            'menge': float(m.group('menge').replace(',', '.')),
            'einheit': m.group('einheit').lower(),
        })
    return results
