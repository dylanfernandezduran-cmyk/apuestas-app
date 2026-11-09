import json, re, shutil, subprocess, pathlib
import pytest
SRC = pathlib.Path(__file__).resolve().parents[1] / "static" / "chat.js"

def _run(expr):
    src = SRC.read_text()
    fns = "".join(m.group(0) for m in re.finditer(r"(?ms)^(?:const CH_STOP=.*?;\n|function chLev\(.*?\n|function chParseMarket\(.*?^}\n|function chAgree\(.*?return null; }\n)", src))
    code = "const chNorm=s=>String(s||'').toLowerCase();\n" + fns + f"\nconsole.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="sin node")

def test_parse_market():
    assert _run("chParseMarket('que te parece tirante +2.5 juegos')") == {"mk": "spread", "line": 2.5}
    assert _run("chParseMarket('munar -1.5 sets')") == {"mk": "sspread", "line": -1.5}
    assert _run("chParseMarket('over 22.5 juegos')") == {"mk": "total", "ou": "over", "line": 22.5}
    assert _run("chParseMarket('munar ml')") == {"mk": "ml"}
    assert _run("chParseMarket('cual es el mejor pick para meter individual')") is None

def test_fuzzy_y_coherencia():
    assert _run("chLev('tiranet','tirante')") == 2 and _run("chLev('tirante','tirante')") == 0
    assert _run("CH_STOP.has('individual') && CH_STOP.has('juegos')") is True
    assert _run("chAgree({total:{side:'over'}},{market:'Total',side:'over'})") is True
    assert _run("chAgree({winner:{side:'home'}},{market:'ML',side:'away'})") is False

def test_sin_filtro_estricto_en_chat():
    s = SRC.read_text(); py = (SRC.parents[1] / "server" / "chat.py").read_text()
    assert "pasa el filtro estricto" not in s and "SÓLO picks con pick_oficial" not in py


def test_intent_entidad_antes_que_mejor_global():
    """«mejor pick en el juego de X» no debe disparar sólo el mejor global: hay entidad que buscar."""
    src = SRC.read_text()
    # el bloque de chBestSingle debe aparecer DESPUÉS de chSearchGames/chFindGame en chLocal
    i = src.find("async function chLocal")
    body = src[i:src.find("async function chAsk")]
    assert "chSearchGames" in body or "chFindGame" in body
    pos_ent = min(x for x in [body.find("chFindGame"), body.find("chSearchGames")] if x >= 0)
    pos_best = body.find("chBestSingle")
    assert pos_ent >= 0 and pos_best > pos_ent
    # frases típicas: la entidad no está en CH_STOP
    assert _run("!CH_STOP.has('etcheverry') && !CH_STOP.has('dahlin')") is True
    # parse no traga toda la frase como mercado
    assert _run("chParseMarket('cual es el mejor pick en el juego de etcheverry')") is None
    assert _run("chParseMarket('que le meto a etcheverry')") is None

def test_frases_juego_de_x():
    src = SRC.read_text()
    assert "Primero entidad" in src
    assert "chBestSingle" in src[src.find("async function chLocal"):src.find("async function chAsk")]
