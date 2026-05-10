"""Unit-Tests für Parser und Format-Erkennung."""
import pytest

from app.formats import detect_format, parse_auto
from app.formats.backring import parse as parse_backring
from app.formats.iceflow import parse as parse_iceflow


# ─── Format-Erkennung ──────────────────────────────────────────────────────


def test_detect_format_iceflow():
    assert detect_format("12345 Milch 3 l\n67890 Butter 250 g") == "IceFlow"


def test_detect_format_backring_separator():
    text = "Header\n***\nKRT 1,00 TIRAMISU N 3 63756"
    assert detect_format(text) == "Backring"


def test_detect_format_backring_firmname():
    assert detect_format("BACKRING Lieferschein Nr. 001") == "Backring"


def test_detect_format_backring_firmname_lowercase():
    assert detect_format("Lieferschein backring 2024") == "Backring"


# ─── IceFlow-Parser ────────────────────────────────────────────────────────

_ICEFLOW_SAMPLE = """\
12345  Milch homogenisiert 3.5 l
10023  Butter 82%  250 g
99001  Joghurt Erdbeere  12 stk
"""


def test_iceflow_parses_products():
    results = parse_iceflow(_ICEFLOW_SAMPLE)
    assert len(results) == 3


def test_iceflow_product_fields():
    results = parse_iceflow(_ICEFLOW_SAMPLE)
    milch = results[0]
    assert milch["produktname"] == "Milch homogenisiert"
    assert milch["menge"] == pytest.approx(3.5)
    assert milch["einheit"] == "l"


def test_iceflow_comma_decimal():
    results = parse_iceflow("55555 Sahne 0,5 l")
    assert len(results) == 1
    assert results[0]["menge"] == pytest.approx(0.5)


def test_iceflow_integer_quantity():
    results = parse_iceflow("11111 Eier 30 stk")
    assert results[0]["menge"] == pytest.approx(30.0)


def test_iceflow_einheit_case_insensitive():
    results = parse_iceflow("22222 Wasser 6 KRT")
    assert results[0]["einheit"] == "krt"


def test_iceflow_no_match_without_artnr():
    results = parse_iceflow("Milch 3 l")
    assert results == []


def test_iceflow_trailing_ocr_noise_stripped():
    # Trailing digits/punctuation after product name should be removed
    results = parse_iceflow("12345 Quark 10% 500 g")
    assert results[0]["produktname"] == "Quark 10%"


def test_iceflow_short_name_skipped():
    results = parse_iceflow("12345 X 1 kg")
    assert results == []


# ─── Backring-Parser ───────────────────────────────────────────────────────

_BACKRING_SAMPLE = """\
***
KRT 1,00 MINI TIRAMISU 150G N 3 63756
STK 6,00 JOGHURT ERDBEERE 150G J 1 54321
"""


def test_backring_parses_products():
    results = parse_backring(_BACKRING_SAMPLE)
    assert len(results) == 2


def test_backring_product_fields():
    results = parse_backring(_BACKRING_SAMPLE)
    tiramisu = results[0]
    assert "TIRAMISU" in tiramisu["produktname"].upper()
    assert tiramisu["menge"] == pytest.approx(1.0)
    assert tiramisu["einheit"] == "karton"


def test_backring_einheit_mapping_stk():
    results = parse_backring("***\nSTK 2,00 PRODUKT N 1 11111")
    assert results[0]["einheit"] == "stk"


def test_backring_einheit_mapping_pac():
    results = parse_backring("***\nPAC 3,00 PRODUKT N 1 22222")
    assert results[0]["einheit"] == "pack"


def test_backring_uses_last_section():
    text = "Header junk\n***\nKRT 1,00 TIRAMISU N 3 63756"
    results = parse_backring(text)
    assert len(results) == 1


def test_backring_no_separator_still_parses():
    text = "KRT 1,00 TIRAMISU N 3 63756"
    results = parse_backring(text)
    assert len(results) == 1


def test_backring_comma_menge():
    results = parse_backring("***\nKRT 12,50 PRODUKT N 5 99999")
    assert results[0]["menge"] == pytest.approx(12.5)


def test_backring_removes_table_artifacts():
    results = parse_backring("***\nKRT 1,00 PRODUKT|NAME N 3 63756")
    assert "|" not in results[0]["produktname"]


# ─── parse_auto ────────────────────────────────────────────────────────────


def test_parse_auto_iceflow():
    fmt, positions = parse_auto("12345 Milch 3 l")
    assert fmt == "IceFlow"
    assert len(positions) == 1


def test_parse_auto_backring():
    fmt, positions = parse_auto("***\nKRT 1,00 TIRAMISU N 3 63756")
    assert fmt == "Backring"
    assert len(positions) == 1
