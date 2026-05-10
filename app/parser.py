from app.formats import parse_auto


def parse_positionen(text: str) -> tuple[str, list[dict]]:
    """Erkennt Format automatisch und gibt (format_typ, positionen) zurück."""
    return parse_auto(text)
