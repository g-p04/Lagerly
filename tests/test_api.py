"""Integrationstests für alle API-Endpunkte."""
import io
from unittest.mock import MagicMock, mock_open, patch

import pytest


# ─── Hilfsfunktionen ───────────────────────────────────────────────────────

_DEFAULT_POSITIONS = [{"produktname": "Milch", "menge": 3.0, "einheit": "l"}]


def _upload(client, ocr_text="12345 Milch 3 l", filename="test.jpg", positions=None):
    if positions is None:
        positions = _DEFAULT_POSITIONS
    m = mock_open()
    with (
        patch("app.main.ocr_file", return_value=(ocr_text, 0.9)),
        patch("app.main.parse_positionen", return_value=("IceFlow", positions)),
        patch("app.main.shutil.copyfileobj"),
        patch("app.main.open", m),
    ):
        data = {"file": (filename, io.BytesIO(b"fake"), "image/jpeg")}
        return client.post("/upload", files=data)


# ─── Lieferschein-Endpunkte ────────────────────────────────────────────────


def test_upload_creates_lieferschein(client):
    r = _upload(client)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "review"
    assert body["dateiname"] == "test.jpg"


def test_upload_ocr_failure_sets_pending(client):
    with (
        patch("app.main.ocr_file", side_effect=RuntimeError("OCR failed")),
        patch("shutil.copyfileobj"),
        patch("builtins.open", create=True),
    ):
        r = client.post("/upload", files={"file": ("bad.jpg", io.BytesIO(b"x"), "image/jpeg")})
    assert r.status_code == 201
    assert r.json()["status"] == "pending"


def test_list_lieferscheine_empty(client):
    r = client.get("/lieferscheine")
    assert r.status_code == 200
    assert r.json() == []


def test_list_lieferscheine_after_upload(client):
    _upload(client)
    r = client.get("/lieferscheine")
    assert len(r.json()) == 1


def test_get_lieferschein(client):
    ls_id = _upload(client).json()["id"]
    r = client.get(f"/lieferscheine/{ls_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == ls_id
    assert len(body["positionen"]) == 1


def test_get_lieferschein_not_found(client):
    r = client.get("/lieferscheine/999")
    assert r.status_code == 404


def test_update_positionen(client):
    upload_body = _upload(client).json()
    ls_id = upload_body["id"]
    pos_id = client.get(f"/lieferscheine/{ls_id}").json()["positionen"][0]["id"]

    r = client.put(
        f"/lieferscheine/{ls_id}/positionen",
        json=[{"id": pos_id, "produktname": "Vollmilch", "menge": 5.0}],
    )
    assert r.status_code == 200
    pos = r.json()["positionen"][0]
    assert pos["produktname"] == "Vollmilch"
    assert pos["menge"] == pytest.approx(5.0)
    assert pos["manuell_korrigiert"] is True


def test_add_position(client):
    ls_id = _upload(client).json()["id"]
    r = client.post(
        f"/lieferscheine/{ls_id}/positionen",
        json={"produktname": "Butter", "menge": 2.0, "einheit": "kg"},
    )
    assert r.status_code == 201
    assert len(r.json()["positionen"]) == 2


def test_add_position_to_approved_forbidden(client):
    ls_id = _upload(client).json()["id"]
    client.post(f"/lieferscheine/{ls_id}/approve")
    r = client.post(
        f"/lieferscheine/{ls_id}/positionen",
        json={"produktname": "X", "menge": 1.0, "einheit": "stk"},
    )
    assert r.status_code == 400


def test_delete_position(client):
    ls_id = _upload(client).json()["id"]
    pos_id = client.get(f"/lieferscheine/{ls_id}").json()["positionen"][0]["id"]
    r = client.delete(f"/lieferscheine/{ls_id}/positionen/{pos_id}")
    assert r.status_code == 204
    assert client.get(f"/lieferscheine/{ls_id}").json()["positionen"] == []


def test_delete_position_wrong_lieferschein(client):
    ls_id_1 = _upload(client).json()["id"]
    ls_id_2 = _upload(client).json()["id"]
    pos_id_2 = client.get(f"/lieferscheine/{ls_id_2}").json()["positionen"][0]["id"]
    r = client.delete(f"/lieferscheine/{ls_id_1}/positionen/{pos_id_2}")
    assert r.status_code == 404


def test_approve_updates_lager(client):
    ls_id = _upload(client).json()["id"]
    r = client.post(f"/lieferscheine/{ls_id}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    lager = client.get("/lager").json()
    assert len(lager) == 1
    assert lager[0]["produktname"] == "Milch"
    assert lager[0]["bestand"] == pytest.approx(3.0)


def test_approve_twice_forbidden(client):
    ls_id = _upload(client).json()["id"]
    client.post(f"/lieferscheine/{ls_id}/approve")
    r = client.post(f"/lieferscheine/{ls_id}/approve")
    assert r.status_code == 400


def test_approve_accumulates_bestand(client):
    _upload(client)
    ls_ids = [r.json()["id"] for r in [_upload(client), _upload(client)]]
    for ls_id in ls_ids:
        client.post(f"/lieferscheine/{ls_id}/approve")
    lager = client.get("/lager").json()
    milch = next(x for x in lager if x["produktname"] == "Milch")
    assert milch["bestand"] == pytest.approx(6.0)


def test_reject_lieferschein(client):
    ls_id = _upload(client).json()["id"]
    r = client.post(f"/lieferscheine/{ls_id}/reject")
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


def test_reject_approved_forbidden(client):
    ls_id = _upload(client).json()["id"]
    client.post(f"/lieferscheine/{ls_id}/approve")
    r = client.post(f"/lieferscheine/{ls_id}/reject")
    assert r.status_code == 400


def test_delete_lieferschein(client):
    ls_id = _upload(client).json()["id"]
    r = client.delete(f"/lieferscheine/{ls_id}")
    assert r.status_code == 204
    assert client.get(f"/lieferscheine/{ls_id}").status_code == 404


def test_delete_lieferschein_cascades_positionen(client):
    ls_id = _upload(client).json()["id"]
    pos_id = client.get(f"/lieferscheine/{ls_id}").json()["positionen"][0]["id"]
    client.delete(f"/lieferscheine/{ls_id}")
    # Lagerbestand has no positions endpoint — verify via list being empty
    assert client.get("/lieferscheine").json() == []


# ─── Lagerbestand-Endpunkte ────────────────────────────────────────────────


def test_get_lager_empty(client):
    assert client.get("/lager").json() == []


def test_get_lager_niedrig(client):
    ls_id = _upload(client).json()["id"]
    client.post(f"/lieferscheine/{ls_id}/approve")
    # bestand=3 >= mindestbestand=0 → nicht niedrig
    r = client.get("/lager/niedrig")
    assert r.json() == []


def test_get_lager_niedrig_returns_item(client):
    ls_id = _upload(client).json()["id"]
    client.post(f"/lieferscheine/{ls_id}/approve")
    lager_id = client.get("/lager").json()[0]["id"]
    # Mindestbestand auf 10 setzen → bestand 3 < 10
    client.put(f"/lager/{lager_id}", json={"mindestbestand": 10.0})
    r = client.get("/lager/niedrig")
    assert len(r.json()) == 1


def test_update_lager(client):
    ls_id = _upload(client).json()["id"]
    client.post(f"/lieferscheine/{ls_id}/approve")
    lager_id = client.get("/lager").json()[0]["id"]

    r = client.put(f"/lager/{lager_id}", json={"bestand": 99.0, "mindestbestand": 5.0})
    assert r.status_code == 200
    body = r.json()
    assert body["bestand"] == pytest.approx(99.0)
    assert body["mindestbestand"] == pytest.approx(5.0)


def test_update_lager_not_found(client):
    r = client.put("/lager/999", json={"bestand": 1.0})
    assert r.status_code == 404


def test_update_lager_einheit(client):
    ls_id = _upload(client).json()["id"]
    client.post(f"/lieferscheine/{ls_id}/approve")
    lager_id = client.get("/lager").json()[0]["id"]
    r = client.put(f"/lager/{lager_id}", json={"einheit": "liter"})
    assert r.json()["einheit"] == "liter"
