"""La calificación de tickets en el navegador (GitHub Pages) da lo mismo que server/grading.py settle()."""
import json, os, subprocess, shutil, pytest
from server import grading as G
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = [("ml", "home", None, 3, 1, "nba"), ("ml", "away", None, 3, 1, "nba"), ("ml", "draw", None, 1, 1, "futbol"), ("ml", "home", None, 1, 1, "futbol"),
         ("spread", "home", -3.5, 110, 100, "nba"), ("spread", "away", 3.5, 110, 100, "nba"), ("spread", "home", -10, 110, 100, "nba"),
         ("spread", "home", -0.25, 1, 1, "futbol"), ("spread", "away", 0.75, 1, 2, "futbol"), ("total", "over", 220.5, 110, 100, "nba"),
         ("total", "under", 2.25, 1, 1, "futbol"), ("total", "over", 2.75, 2, 1, "futbol"), ("btts", "yes", None, 1, 1, "futbol"), ("btts", "no", None, 2, 0, "futbol")]

@pytest.mark.skipif(not shutil.which("node"), reason="node no disponible")
def test_js_settle_matches_python():
    src = open(os.path.join(ROOT, "static", "ticket.js"), encoding="utf-8").read()
    stub = "var localStorage={getItem:()=>null,setItem:()=>{}};var document={addEventListener(){},getElementById:()=>null,createElement:()=>({}),body:{appendChild(){}}};var STATIC=false;"
    js = stub + src + "\nconst C=" + json.dumps(CASES) + ";console.log(JSON.stringify(C.map(([m,s,l,h,a,sp])=>tkSettle({market:m,selection:s,line:l,sport:sp},h,a))));"
    out = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    exp = [G.settle(m, s, l, dict(home=h, away=a), three_way=(sp == "futbol")) for m, s, l, h, a, sp in CASES]
    assert out == exp
