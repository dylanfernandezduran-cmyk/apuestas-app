"""pt90u: Ambos anotan (BTTS), versión estática para GitHub Pages y chat IA (sin llave)."""
import asyncio, importlib.util, json, re, subprocess
from pathlib import Path
from server import prediction as P, model as M, grading as G, props as PR, chat as CH
from test_prediccion import soc_model, game

ROOT = Path(__file__).resolve().parent.parent

def bmodel(lh, la):
    m = soc_model(lh, la)
    pm = lambda l: M.pois_pmf(l, 12)
    mat = [[pm(lh)[i] * pm(la)[j] for j in range(13)] for i in range(13)]; z = sum(map(sum, mat))
    m["p_btts"] = sum(mat[i][j] for i in range(1, 13) for j in range(1, 13)) / z
    return m

def test_p_btts_del_modelo_poisson_real():
    class R: pass
    m = M.soccer_model({"att": {"1": 1.2, "2": .9}, "def": {"1": .9, "2": 1.1}, "lg_home": 1.5, "lg_away": 1.2, "n": {"1": 10, "2": 10}}, "1", "2")
    lh, la = m["lam_home"], m["lam_away"]
    import math
    assert abs(m["p_btts"] - (1 - math.exp(-lh)) * (1 - math.exp(-la))) < 1e-3       # independencia Poisson: P(ambos) = (1-e^-λh)(1-e^-λa)

def _ok_btts(p):
    h, a = p["score"]["home"], p["score"]["away"]
    assert (p["btts"]["side"] == "yes") == (h > 0 and a > 0)

def test_marcador_concuerda_con_pick_btts():
    pk = lambda side: dict(lean=dict(market="BTTS", side=side, line=None, status="PICK"), status="PICK", candidates=[])
    p = P.build(game(), bmodel(2.2, .6), None, "soccer", picks=pk("yes"))
    assert p["btts"]["side"] == "yes" and p["btts"]["aligned"] == "pick" and p["score"]["away"] > 0 and p["score"]["home"] > 0
    p = P.build(game(), bmodel(1.4, 1.4), None, "soccer", picks=pk("no"))
    assert p["btts"]["side"] == "no" and min(p["score"]["home"], p["score"]["away"]) == 0
    for lh in (.6, 1.0, 1.6, 2.4):
        for la in (.5, 1.1, 1.9):
            _ok_btts(P.build(game(), bmodel(lh, la), None, "soccer"))

def test_btts_con_over_35_y_pick_btts_no_siguen_coherentes():
    pk = dict(lean=dict(market="Total", side="over", line=3.5, status="PICK"), status="PICK",
              candidates=[dict(market="BTTS", side="no", status="PICK")])
    p = P.build(game(), bmodel(2.0, 1.2), dict(total=dict(over=dict(line=3.5)), book="X"), "soccer", picks=pk)
    h, a = p["score"]["home"], p["score"]["away"]
    assert h + a >= 4 and min(h, a) == 0 and p["btts"]["side"] == "no"                 # p. ej. 4-0: cumple Over 3.5 y BTTS No

def test_candidato_btts_con_cuota_real_y_grading():
    m = bmodel(1.6, 1.3); m["sample"] = 1.0
    odds = dict(ml={}, spread={}, total={}, nv=dict(btts=dict(yes=.55, no=.45)), btts=dict(yes=-120, no=100))
    c = [x for x in M.build_candidates(m, odds, "A", "B") if x["market"] == "BTTS"]
    assert {x["side"] for x in c} == {"yes", "no"} and all(x["price"] in (-120, 100) for x in c)
    assert G.settle("btts", "yes", None, dict(home=2, away=1)) == "GANADO" and G.settle("btts", "yes", None, dict(home=2, away=0)) == "PERDIDO"
    assert G.settle("btts", "no", None, dict(home=0, away=0)) == "GANADO"
    assert P.grade_row(dict(sport="futbol", pred=dict(winner=dict(side="home"), score=dict(home=2, away=1), btts=dict(side="yes"))),
                       dict(state="final", home=2, away=1))["r_btts"] == "GANADO"

def test_parse_btts_draftkings_par_si_no():
    it = lambda am_c, am_o: {"type": {"name": "Both Teams To Score"}, "current": {"over": {"american": am_c}}, "open": {"over": {"american": am_o}}, "lastUpdated": "x"}
    b = PR.parse_btts([it("-200", "-285"), it("+155", "+195")])
    assert (b["yes"], b["no"], b["open_yes"], b["open_no"]) == (-200, 155, -285, 195)
    assert PR.parse_btts([it("-200", "-285")]) is None                                 # sin par: no se adivina

def test_clave_estatica_python_igual_a_js():
    spec = importlib.util.spec_from_file_location("bs", ROOT / "scripts" / "build_static.py")
    src = (ROOT / "scripts" / "build_static.py").read_text()
    ns = {}; exec(src[src.index("def key_for"):src.index("STATS = ")], {"re": re}, ns)
    js = (ROOT / "static" / "app.js").read_text()
    fn = js[js.index("function staticUrl"):js.index("async function api(")]
    cases = ["/api/games?league=uefa.champions", "/api/game/nfl/401873038", "/api/picks?scope=24h", "/api/props/nba/1", "/api/league_brief?league=nba", "/api/home"]
    out = subprocess.run(["node", "-e", fn + "\nconsole.log(JSON.stringify(" + json.dumps(cases) + ".map(staticUrl)))"], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [ns["key_for"](c) for c in cases]

def test_chat_sin_llave_responde_llm_false(monkeypatch):
    for k in ("NRNM_LLM_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"): monkeypatch.delenv(k, raising=False)
    assert CH.status() == dict(llm=False, provider=None, model=None)
    assert asyncio.run(CH.answer("hola")) == dict(llm=False)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert CH.status()["llm"] is True and CH.status()["provider"] == "groq"

def test_sin_secretos_en_el_repo_y_workflow():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    pat = re.compile(r"(gsk_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY)")
    for f in files:
        p = ROOT / f
        if p.suffix in (".png", ".jpg", ".ico", ".webp", ".db") or not p.is_file(): continue
        assert not pat.search(p.read_text(errors="ignore")), f
    wf = (ROOT / "deploy" / "github-pages.yml").read_text()
    assert "schedule" in wf and "deploy-pages" in wf and "build_static.py" in wf
