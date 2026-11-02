"""Que el detalle nunca se quede girando: 403 de ESPN -> respaldo con curl; el frontend corta por tiempo y muestra error + reintentar."""
import asyncio, os, re, shutil, subprocess, json
import httpx, pytest
from server import cache

ROOT = os.path.join(os.path.dirname(__file__), "..")

def test_get_json_usa_curl_si_httpx_recibe_403(monkeypatch):
    calls = {"curl": 0}
    async def fake_curl(url, params=None, headers=None):
        calls["curl"] += 1; assert "event=1" in str(httpx.URL(url).copy_merge_params(params or {})); return {"header": {"ok": True}}
    monkeypatch.setattr(cache, "_curl_get", fake_curl)
    monkeypatch.setattr(cache, "_store", {}); monkeypatch.setattr(cache, "_curl_until", 0.0)
    monkeypatch.setattr(cache, "_client", httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(403, text="<HTML>Access Denied</HTML>"))))
    r = asyncio.run(cache.get_json("https://site.api.espn.com/x/summary", ttl=0, params={"event": "1"}))
    assert r == {"header": {"ok": True}} and calls["curl"] == 1
    # ya marcado como bloqueado: las siguientes van directo a curl sin pegarle a httpx
    r = asyncio.run(cache.get_json("https://site.api.espn.com/x/summary2", ttl=0, params={"event": "1"}))
    assert r == {"header": {"ok": True}} and calls["curl"] == 2

def test_get_json_sigue_devolviendo_none_si_todo_falla(monkeypatch):
    async def no_curl(*a, **k): return None
    monkeypatch.setattr(cache, "_curl_get", no_curl); monkeypatch.setattr(cache, "_store", {}); monkeypatch.setattr(cache, "_curl_until", 0.0)
    monkeypatch.setattr(cache, "_client", httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(403))))
    assert asyncio.run(cache.get_json("https://site.api.espn.com/y", ttl=0)) is None

@pytest.mark.skipif(not shutil.which("node"), reason="sin node")
def test_frontend_api_corta_por_tiempo_y_ruta_muestra_reintentar():
    src = open(os.path.join(ROOT, "static", "app.js"), encoding="utf-8").read()
    a = src.index("const API_TIMEOUT_MS"); b = src.index("const errBox")
    js = """
global.esc = s => String(s);
global.fetch = (u, o) => new Promise((res, rej) => { o.signal.addEventListener('abort', () => { const e = new Error('abort'); e.name = 'AbortError'; rej(e); }); });
""" + src[a:b] + """
api('/api/game/x/1', 30).then(() => console.log('NO'), e => console.log(e.message));
"""
    out = subprocess.check_output(["node", "-e", js], text=True)
    assert "tardó demasiado" in out
    # las vistas se esperan dentro del try (si no, un rechazo se escapa y la pantalla queda en «Analizando…»)
    assert "return await viewGame(h[1], h[2])" in src and "errBox(e.message)" in src and "↻ Reintentar" in src
