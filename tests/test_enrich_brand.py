"""Descanso (back-to-back) y marca/PWA (manifest, servidor, cambio de marca por BRAND)."""
import json
from fastapi.testclient import TestClient
from server import enrich as E

def g(d): return dict(date=d)

def test_rest_days_and_back_to_back():
    # juego 2 nov 19:00 CDMX = 3 nov 01:00Z; ayer 1 nov 18:00 CDMX
    r = E.rest_info([g("2026-11-01T23:00Z"), g("2026-10-30T01:00Z")], "2026-11-03T01:00Z", "basketball")
    assert r["days"] == 0 and r["b2b"] and r["n7"] == 2 and r["last"] == "2026-11-01"
    r = E.rest_info([g("2026-10-29T23:00Z")], "2026-11-03T01:00Z", "basketball")
    assert r["days"] == 3 and not r["b2b"]
    assert E.rest_info([g("2026-11-01T23:00Z")], "2026-11-03T01:00Z", "baseball")["b2b"] is False   # sólo NBA/NHL
    assert E.rest_info([], "2026-11-03T01:00Z", "basketball") is None
    assert E.rest_info([g("2026-11-05T01:00Z")], "2026-11-03T01:00Z", "basketball") is None          # futuros no cuentan

def test_brand_manifest_and_index(monkeypatch):
    from server import main
    c = TestClient(main.app)
    b = c.get("/api/brand").json()
    assert b["id"] == "ventaja" and set(b["options"]) == {"ventaja", "pizarra", "vigia", "avizor", "atalaya", "zahori", "lince", "nrnm", "nrnm_oro", "tri_bola", "tri_rayos", "tri_avizor", "tri_badge"}
    m = c.get("/manifest.webmanifest").json()
    assert m["display"] == "standalone" and m["short_name"] == "Ventaja" and any(i["purpose"] == "maskable" for i in m["icons"])
    html = c.get("/").text
    assert "Ventaja" in html and "__NAME__" not in html and "__GLYPH__" not in html and "apple-touch-icon" in html and "apple-mobile-web-app-capable" in html
    sw = c.get("/sw.js"); assert sw.status_code == 200 and sw.headers["service-worker-allowed"] == "/"
    monkeypatch.setenv("BRAND", "pizarra")
    assert c.get("/api/brand").json()["name"] == "Pizarra" and c.get("/manifest.webmanifest").json()["short_name"] == "Pizarra"
    monkeypatch.setenv("BRAND", "no-existe")
    assert c.get("/api/brand").json()["id"] == "ventaja"

def test_brand_assets_exist():
    import os
    root = os.path.join(os.path.dirname(__file__), "..", "static", "brand")
    for k in json.load(open(os.path.join(root, "brand.json")))["options"]: assert os.path.exists(os.path.join(root, k, "glyph.svg"))
    for f in ("icon-192.png", "icon-512.png", "maskable-512.png", "apple-touch-icon.png", "favicon-32.png"): assert os.path.exists(os.path.join(root, "icons", f))
