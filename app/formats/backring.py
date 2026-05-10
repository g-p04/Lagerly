"""
Backring-Lieferschein-Format.

Abschnitte durch Zeilen aus '*'-Zeichen getrennt.
Spaltenreihenfolge (aus OCR-Beobachtungen realer Belege):
  VP-Inhalt  VP-Bez  Liefermenge  Artikelbezeichnung  [Flag]  Gew.inKg  Art.Nr.

  - VP-Inhalt: Inhalt pro Verpackungseinheit (z.B. 6, 12 — OCR liest "1" ggf. als "L")
  - VP-Bez: Verpackungstyp (KRT, STK, PAC …) → wird als Einheit gespeichert
  - Liefermenge: immer Dezimalzahl mit Komma (z.B. 1,00 / 5,00)
  - Artikelbezeichnung: beliebiger Text
  - Flag: optionaler Einzelbuchstabe (handschriftliches Zeichen, z.B. N/J)
  - Gew.inKg: Gewicht (ignoriert)
  - Art.Nr.: 4–8 Ziffern am Zeilenende

Beispiel:
  1 KRT 1,00 MINI TIRAMISU 150G  N  3  63756
  6 STK 2,00 JOGHURT ERDBEERE 150G  J  1  54321
"""
import re

_SEP = re.compile(r"^\s*\*{3,}\s*$", re.MULTILINE)

# Normalisierung VP-Bez → interne Einheitswerte
_EINHEIT_MAP: dict[str, str] = {
    "krt": "karton",
    "krtn": "karton",
    "st": "stk",
    "stk": "stk",
    "stue": "stueck",
    "pac": "pack",
    "pck": "pack",
    "pack": "pack",
    "kg": "kg",
    "g": "g",
    "l": "l",
    "ltr": "liter",
    "liter": "liter",
    "ml": "ml",
}

# Keine ^ / $ Anker: OCR-Rauschen am Zeilenanfang und -ende wird ignoriert.
# einheit muss mit Buchstabe beginnen → verhindert Ziffernfolgen als false positive.
# Liefermenge hat immer genau 2 Dezimalstellen (1,00 / 6,00 / 12,50).
_LINE = re.compile(
    r"(?P<einheit>[A-Za-zäöüÄÖÜß]\w*)"  # VP-Bez: beginnt mit Buchstabe
    r"\s+(?P<menge>\d+[.,]\d{2})"        # Liefermenge: genau 2 Dezimalstellen
    r"\s+(?P<rest>.+)"                    # Artikelbezeichnung + optionaler Flag (greedy)
    r"\s+\d+[.,]?\d*"                    # Gew.inKg (ignoriert)
    r"\s+(?P<artnr>\d{4,8})",            # Art.Nr. (kein $ – trailing OCR-Rauschen erlaubt)
    re.IGNORECASE | re.MULTILINE,
)


def _clean_name(rest: str) -> str:
    name = rest.strip()
    # Flag am Ende entfernen: Einzelbuchstabe ggf. mit Sonderzeichen-Prefix (&J, N, Q)
    name = re.sub(r"\s+[&@#%]*[A-Z]{1,2}\s*$", "", name)
    # Einzel- oder zweistellige Zahl am Ende (Gew.inKg-Artefakt bei mehrdeutiger Backtracking-Grenze)
    name = re.sub(r"\s+\d{1,2}\s*$", "", name)
    # Sonderzeichen am Ende (OCR-Artefakte aus Handschrift/Stempeln)
    name = re.sub(r"[^A-Za-z0-9äöüÄÖÜß\s]+$", "", name).strip()
    return name


def parse(text: str) -> list[dict]:
    # Datenbereich nach dem letzten '*'-Trenner
    parts = _SEP.split(text)
    data = parts[-1] if len(parts) > 1 else text
    # Tabellenlinien-Artefakte entfernen (OCR liest |, /, \, [] als Zeichen)
    data = re.sub(r"[\[\]\\|/]", " ", data)

    results = []
    for m in _LINE.finditer(data):
        name = _clean_name(m.group("rest"))
        if not name:
            continue
        einheit_raw = m.group("einheit").lower()
        einheit = _EINHEIT_MAP.get(einheit_raw, einheit_raw)
        results.append(
            {
                "produktname": name,
                "menge": float(m.group("menge").replace(",", ".")),
                "einheit": einheit,
            }
        )
    return results
