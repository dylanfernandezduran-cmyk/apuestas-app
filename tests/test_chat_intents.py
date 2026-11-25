"""Batería de intenciones del chat: liga con typos, filtro, EV, sólo PICK, hoy/mañana, no saltar de deporte."""
import json, shutil, subprocess, pathlib, datetime
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "static" / "chat.js"

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="sin node")

HARNESS = r"""
const TZ='America/Mexico_City';
const esc=s=>String(s);
const CH={};
function chNorm(s){ return String(s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,''); }
function chPct(p){ return p==null?'—':Math.round(p*100)+'%'; }
function chWhen(iso){ return iso||''; }
function chVs(g){ return (g.sport==='futbol'||g.sport==='tenis')?`${g.home.name} vs ${g.away.name}`:`${g.away.name} @ ${g.home.name}`; }
function chGame(it){ return chVs(it.game); }
function chLink(g){ return '#/juego/'+(g.league||'')+'/'+(g.id||''); }
function chAgree(pr,l){ if(!pr||!l) return null;
  if(l.market==='Total'&&pr.total&&pr.total.side) return pr.total.side===l.side;
  if(l.market==='Spread'&&pr.spread&&pr.spread.side) return pr.spread.side===l.side;
  if(l.market==='ML'&&pr.winner&&pr.winner.side) return pr.winner.side===l.side;
  if(l.market==='BTTS'&&pr.btts&&pr.btts.side) return pr.btts.side===l.side;
  return null; }
function chLev(a,b){ if(Math.abs(a.length-b.length)>2) return 9; const d=[...Array(b.length+1).keys()]; for(let i=1;i<=a.length;i++){ let pv=d[0]; d[0]=i; for(let j=1;j<=b.length;j++){ const t=d[j]; d[j]=Math.min(d[j]+1,d[j-1]+1,pv+(a[i-1]===b[j-1]?0:1)); pv=t; } } return d[b.length]; }
function chPickLine(it){
  const l=it.lean||{}; if(!l.label) return `${chGame(it)}: sin pick (sin línea de mercado).`;
  const conf=it.confidence&&it.confidence.level?` · confianza ${esc(it.confidence.level)}`:'';
  const ag=chAgree(it.pred,l);
  const conc=ag===true?' · concuerda con la predicción':(ag===false?' · no concuerda con la predicción':'');
  return `• ${esc(chGame(it))} <b>${esc(l.label)}</b> ${esc(chEvTxt(l.ev))} · ${esc(it.status)}${conf}${conc}`;
}
HELPERS
const ITEMS=JSON.parse(process.env.CH_ITEMS||'[]');
// node -e 'code' q mode → argv is [node, q, mode]
const q=process.argv[1];
const mode=process.argv[2]||'answer';
if(mode==='scope') console.log(JSON.stringify(chScope(chNorm(q))));
else if(mode==='intent') console.log(JSON.stringify(chListIntent(chNorm(q))));
else console.log(JSON.stringify(chBestAnswerFromItems(ITEMS, chNorm(q))));
"""


def _helpers():
    src = SRC.read_text()
    a = src.find("/* --- intent helpers (testable) --- */")
    b = src.find("/* --- end intent helpers --- */")
    assert a >= 0 and b > a
    return src[a:b + len("/* --- end intent helpers --- */")]


def _items():
    # fechas relativas a ahora (CDMX): hoy, mañana, y un NHL hoy
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-6)))
    def iso(h, day=0):
        d = today.replace(hour=h, minute=0, second=0, microsecond=0) + datetime.timedelta(days=day)
        return d.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    def game(league, sport, home, away, hid, day=0, hour=15):
        return dict(id=hid, league=league, sport=sport, date=iso(hour, day),
                    home=dict(name=home, abbr=home[:3].upper()),
                    away=dict(name=away, abbr=away[:3].upper()))
    def item(g, status, ev, edge, side="home", published=None, conf="Media", agree=True, reason=None, label=None):
        published = (status == "PICK") if published is None else published
        lean = dict(market="ML", side=side, label=label or (g["home"]["name"]+" ML"), ev=ev, edge=edge,
                    p_final=0.55, p_nv=0.48, price=-110, price_txt="-110")
        pred = dict(winner=dict(side=side if agree else ("away" if side == "home" else "home"), p=0.55, probs={}),
                    score=dict(home=2, away=1), total=dict(side="under", label="Menos de 2.5"))
        return dict(game=g, lean=lean, status=status, published=published, approved=published,
                    confidence=dict(level=conf), pred=pred, discard_reason=reason)
    return [
        item(game("uefa.nations","futbol","Germany","Netherlands","n1",0,19), "REVISAR", -6.4, 0.3, reason="divergencia alta"),
        item(game("uefa.nations","futbol","Switzerland","Scotland","n2",0,19), "PASS", -8.0, -0.2, reason="EV≤0"),
        item(game("uefa.nations","futbol","Greece","Serbia","n3",1,19), "PICK", 4.2, 3.1, conf="Alta"),
        item(game("uefa.nations","futbol","Wales","Portugal","n4",1,19), "PICK", 7.5, 2.0, conf="Media"),
        item(game("uefa.champions","futbol","Real Madrid","Liverpool","c1",0,16), "PICK", 12.0, 5.0, conf="Alta"),
        item(game("concacaf.nations.league","futbol","Mexico","Jamaica","m1",1,20), "REVISAR", -5.0, 0.2, reason="muestra pequeña"),
        item(game("fifa.friendly","futbol","Argentina","Costa Rica","f1",1,17), "PASS", -3.0, 0.1),
        item(game("fifa.friendly","futbol","Brazil","Singapore","f2",1,4), "PICK", 2.2, 1.1, conf="Baja"),
        item(game("eng.1","futbol","Arsenal","Chelsea","e1",0,11), "PICK", 3.3, 2.2, conf="Media"),
        item(game("mex.1","futbol","América","Pumas","x1",0,20), "PICK", 1.8, 1.4, conf="Media"),
        item(game("ger.1","futbol","Bayern","Dortmund","g1",0,14), "PICK", 5.0, 2.5, conf="Alta"),
        item(game("esp.1","futbol","Barcelona","Valencia","s1",0,15), "REVISAR", -2.0, 0.4),
        item(game("ita.1","futbol","Inter","Milan","i1",0,14), "PICK", 2.5, 1.0, conf="Baja"),
        item(game("nba","nba","Toronto Raptors","New York Knicks","b1",0,19), "PASS", -0.15, 1.8, label="Toronto Raptors +4.5"),
        item(game("nba","nba","Milwaukee Bucks","Atlanta Hawks","b2",0,19), "REVISAR", -3.0, 2.0),
        item(game("nhl","nhl","Edmonton Oilers","Philadelphia Flyers","h1",0,18), "PASS", -2.6, 0.6, label="Edmonton Oilers ML"),
        item(game("nfl","nfl","Kansas City Chiefs","Buffalo Bills","f3",0,19), "PICK", 6.1, 4.0, conf="Alta"),
        item(game("mlb","mlb","Yankees","Red Sox","y1",1,19), "PICK", 2.0, 1.2, conf="Media"),
        item(game("atp","tenis","Alcaraz","Sinner","t1",0,13), "PASS", -1.2, 0.2),
        # pick que contradice la predicción: no debe entrar a 'mejores'
        item(game("uefa.nations","futbol","Italy","Belgium","n5",0,16), "PICK", 20.0, 8.0, conf="Alta", agree=False, published=True, label="Belgium ML"),
    ]


def _run(q, mode="answer", items=None):
    helpers = _helpers()
    code = HARNESS.replace("HELPERS", helpers)
    env = dict(**{k: v for k, v in __import__("os").environ.items()}, CH_ITEMS=json.dumps(items if items is not None else _items()))
    r = subprocess.run(["node", "-e", code, q, mode], capture_output=True, text=True, env=env)
    if r.returncode:
        raise AssertionError(r.stderr or r.stdout)
    return json.loads(r.stdout)


# ---------- batería (~30 consultas reales con typos) ----------
CASES = [
    ("dame los mejores picks de uefa liga de naciines", {"must": ["Liga de Naciones UEFA", "Wales ML", "Greece ML"], "must_not": ["Oilers", "Raptors", "Chiefs", "por edge", "Real Madrid"], "scope_leagues": ["uefa.nations"]}),
    ("mejores picks de liga de naciones", {"must": ["Liga de Naciones UEFA"], "must_not": ["Oilers", "Raptors"]}),
    ("picks de la nations league", {"must": ["Liga de Naciones UEFA"], "must_not": ["Oilers"]}),
    ("mejores picks de concacaf", {"must": ["No hay picks aprobados", "Liga de Naciones CONCACAF", "Mexico"], "must_not": ["Oilers", "Wales ML", "Raptors"]}),
    ("picks de amistosos", {"must": ["Amistosos", "Brazil"], "must_not": ["Oilers", "Wales ML"]}),
    ("mejores picks de la premier", {"must": ["Arsenal"], "must_not": ["Oilers", "Wales ML"]}),
    ("mejores picks de liga mx", {"must": ["América"], "must_not": ["Oilers", "Arsenal"]}),
    ("picks de champions", {"must": ["Real Madrid"], "must_not": ["Wales ML", "Oilers"]}),
    ("mejores picks de nba hoy", {"must": ["No hay picks aprobados", "NBA"], "must_not": ["Chiefs", "Wales ML", "Mejores picks (por EV"]}),
    ("mejores picks de la nfl", {"must": ["Chiefs"], "must_not": ["Raptors", "Wales ML"]}),
    ("picks de hockey", {"must": ["No hay picks aprobados", "NHL"], "must_not": ["Chiefs"]}),
    ("picks de beisbol", {"must": ["Yankees"], "must_not": ["Chiefs", "Wales"]}),
    ("mejores picks de tenis", {"must": ["No hay picks aprobados", "tenis"], "must_not": ["Chiefs"]}),
    ("mejores picks de hoy de futbol", {"must": ["por EV y confianza"], "must_not": ["Oilers", "Yankees"]}),
    ("que me recomiendas en la bundesliga", {"must": ["Bayern"], "must_not": ["Oilers"]}),
    ("picks de serie a", {"must": ["Inter"], "must_not": ["Oilers"]}),
    ("mejores picks de laliga", {"must": ["No hay picks aprobados", "LaLiga", "Barcelona"], "must_not": ["Oilers"]}),
    ("picks de uefa", {"must": ["Liga de Naciones UEFA"], "may_champions": True, "must_not": ["Oilers", "Raptors"]}),
    ("mejores picks de burdesliga", {"must": ["Bayern"], "must_not": ["Oilers"]}),  # typo bundesliga
    ("picks de la premir league", {"must": ["Arsenal"], "must_not": ["Oilers"]}),
    ("mejores picks de nacioens", {"must": ["Liga de Naciones UEFA"], "must_not": ["Oilers"]}),
    ("picks de champins", {"must": ["Real Madrid"], "must_not": ["Wales ML"]}),
    ("mejores picks de amistozos", {"must": ["Amistosos"], "must_not": ["Oilers"]}),
    ("mejores picks", {"must": ["por EV y confianza"], "must_not": ["por edge", "Oilers", "Raptors", "Belgium ML"]}),
    ("mejores picks hoy", {"date": "hoy", "must_not": ["por edge", "Oilers"]}),
    ("mejores picks manana", {"date": "manana", "must_not": ["Oilers"]}),
    ("mejores picks mañana", {"date": "manana", "must_not": ["Oilers"]}),
    ("dame los mejores picks de uefa liga de naciones", {"must": ["Liga de Naciones UEFA"], "must_not": ["Oilers"]}),
    ("picks para la liga de campeones", {"must": ["Real Madrid"], "must_not": ["Wales ML"]}),
    ("que apuesto en los amistosos internacionales", {"must": ["Amistosos"], "must_not": ["Oilers"]}),
]


def test_bateria_intenciones_espanol_con_typos():
    failed = []
    for q, exp in CASES:
        scope = _run(q, "scope")
        ans = _run(q, "answer")
        if "scope_leagues" in exp and set(scope.get("leagues") or []) != set(exp["scope_leagues"]):
            failed.append((q, "scope", scope, exp["scope_leagues"]))
            continue
        if exp.get("date") and scope.get("date") != exp["date"]:
            failed.append((q, "date", scope, exp["date"]))
            continue
        text = ans if isinstance(ans, str) else json.dumps(ans)
        for m in exp.get("must") or []:
            if m not in text:
                failed.append((q, "missing", m, text[:400]))
                break
        else:
            for m in exp.get("must_not") or []:
                if m in text:
                    failed.append((q, "forbidden", m, text[:400]))
                    break
    assert not failed, "fallos %d/%d:\n%s" % (len(failed), len(CASES), "\n".join(map(str, failed)))


def test_uefa_typo_no_salta_a_nba_y_ordena_por_ev():
    q = "dame los mejores picks de uefa liga de naciines"
    assert _run(q, "intent") == "best"
    scope = _run(q, "scope")
    assert scope["leagues"] == ["uefa.nations"]
    ans = _run(q)
    assert "Wales ML" in ans and "Greece ML" in ans
    assert ans.index("Wales ML") < ans.index("Greece ML")  # EV 7.5 antes que 4.2
    assert "Belgium ML" not in ans  # contradice predicción
    assert "Oilers" not in ans and "Raptors" not in ans and "por edge" not in ans
    assert "Lado del modelo, no aprobado" in ans  # REVISAR/PASS de la misma liga, aparte


def test_solo_pick_en_lista_global_sin_pass():
    ans = _run("mejores picks")
    assert "Mejores picks (por EV y confianza" in ans
    assert "Oilers" not in ans and "Raptors" not in ans
    assert "Belgium ML" not in ans
    assert "Chiefs" in ans or "Bayern" in ans or "Wales" in ans


def test_manana_no_lista_juegos_de_hoy():
    ans = _run("mejores picks manana")
    assert "Arsenal" not in ans and "Chiefs" not in ans  # hoy
    assert "Wales ML" in ans or "Brazil" in ans  # mañana


def test_list_intent_no_traga_el_record_ni_parlay():
    assert _run("arma un parlay de nba", "intent") == "parlay"
    # récord no es list intent
    assert _run("record de hoy", "intent") is None
