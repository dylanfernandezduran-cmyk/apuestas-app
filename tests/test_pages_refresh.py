import re
"""Cadencia de Pages, huella estable y red-primero para los JSON de datos."""
import json, os, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def test_cron_escalonado_y_dispatch():
    yml = (ROOT / "scripts/pages.workflow.yml").read_text()
    assert 'cron: "7,22,37,52 * * * *"' in yml
    assert 'cron: "17 8 * * *"' in yml
    assert "*/10 * * * *" not in yml
    assert "refresh-pages" in yml
    assert "group: nrnm-pages" in yml
    assert "cancel-in-progress: false" in yml
    assert "ODDS_TTL_FLOOR" in yml and "600" in yml
    assert "needs.build.outputs.changed" in yml
    assert (ROOT / "scripts/trigger_pages_refresh.sh").is_file()
    assert (ROOT / "scripts/pages.workflow.yml").is_file()


def test_content_hash_ignora_now_y_built():
    from site_hash import content_hash
    d = Path(tempfile.mkdtemp())
    data = d / "data"
    data.mkdir()
    payload = {"date": "2026-11-16", "now": 1, "items": [{"pick": "A", "updated": 9}]}
    (data / "picks.json").write_text(json.dumps(payload))
    (data / "build.json").write_text(json.dumps({"built": "x", "seconds": 1, "hash": "old"}))
    a = content_hash(str(d))
    payload["now"] = 999
    payload["items"][0]["updated"] = 10
    (data / "picks.json").write_text(json.dumps(payload))
    (data / "build.json").write_text(json.dumps({"built": "y", "seconds": 2}))
    assert content_hash(str(d)) == a
    payload["items"][0]["pick"] = "B"
    (data / "picks.json").write_text(json.dumps(payload))
    assert content_hash(str(d)) != a


def test_http_budget_sirve_cache_vieja_sin_inventar():
    import asyncio
    from server import cache as C
    C._store.clear(); C._budget_used.clear()
    C.STATS["stale_budget"] = 0
    url = "https://api.actionnetwork.com/web/v2/scoreboard/publicbetting/soccer"
    C._store[C._key(url, None)] = (time.time() - 9999, {"games": [{"id": 1}]})
    os.environ["BUDGET_AN"] = "0"
    try:
        got = asyncio.run(C.get_json(url, ttl=1))
        assert got == {"games": [{"id": 1}]}
        assert C.STATS["stale_budget"] >= 1
    finally:
        os.environ.pop("BUDGET_AN", None)
        C._store.clear(); C._budget_used.clear()


def test_sw_network_first_para_data_json_y_banner_de_antiguedad():
    sw = (ROOT / "static/sw.js").read_text()
    app = (ROOT / "static/app.js").read_text()
    assert re.search(r"shell-v\d+", sw)
    assert "data-v1" in sw and "no-store" in sw and "isDataJson" in sw
    assert "fmtAgo" in app and "actualizado hace" in app
    assert "data/build.json" in app
    assert "se actualizan cada ~10-15 min" not in app
