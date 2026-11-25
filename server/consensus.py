"""Consenso público de handicappers: Covers Consensus (contests.covers.com), página pública.
Es el % de picks de los concursantes de Covers por lado (contra el spread / línea de carrera / puck line).
Se cita la fuente con su URL; si no hay coincidencia exacta del juego no se muestra nada (nunca se inventa)."""
import re, html as H, time
from .cache import fetch_bytes

SLUG = {"nba": "nba", "nfl": "nfl", "nhl": "nhl", "mlb": "mlb"}
URL = "https://contests.covers.com/consensus/topconsensus/{slug}/overall"
_C = {}

def _txt(x): return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", x))).strip()

def parse(page):
    i = page.find("<table")
    if i < 0: return []
    t = page[i:page.find("</table>", i)]
    out = []
    for r in t.split("<tr")[1:]:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        if len(tds) < 5: continue
        alts = re.findall(r'alt="([^"]*)"', tds[0]); logos = re.findall(r'/new_logos/\w+/([\w-]+)\.png', tds[0])
        pct = [int(x) for x in re.findall(r"(\d+)%", tds[2])]
        lines = [x.strip() for x in _txt(tds[3].replace("<br />", "|")).split("|")]
        picks = [x.strip() for x in _txt(tds[4].replace("<br />", "|")).split("|")]
        det = re.search(r'href="(/consensus/matchupconsensusdetails/[^"]+)"', r)
        if len(alts) < 2 or len(pct) < 2: continue
        out.append(dict(away=dict(name=re.sub(r"\s*Picks$", "", alts[0]), abbr=(logos[0] if logos else "").lower(), pct=pct[0], line=lines[0] if lines else None, picks=int(picks[0]) if picks and picks[0].isdigit() else None),
                        home=dict(name=re.sub(r"\s*Picks$", "", alts[1]), abbr=(logos[1] if len(logos) > 1 else "").lower(), pct=pct[1], line=lines[1] if len(lines) > 1 else None, picks=int(picks[1]) if len(picks) > 1 and picks[1].isdigit() else None),
                        when=_txt(tds[1].replace("<br />", " ")), url="https://contests.covers.com" + det.group(1) if det else None))
    return out

def _same(cv, team):
    ab = (team.get("abbr") or "").lower(); nm = (team.get("name") or "").lower()
    if ab and ab == cv["abbr"]: return True
    nick = nm.split()[-1] if nm else ""
    return bool(nick) and nick in cv["name"].lower()

async def rows(league):
    slug = SLUG.get(league)
    if not slug: return []
    c = _C.get(league)
    if c and time.time() - c[0] < 900: return c[1]
    try:
        res = await fetch_bytes(URL.format(slug=slug), headers={"User-Agent": "Mozilla/5.0"})
        if not res: raise RuntimeError("sin respuesta")
        rs = parse(res[0].decode("utf-8", "replace"))
    except Exception:
        rs = (c or (0, []))[1]
    _C[league] = (time.time(), rs)
    return rs

MON = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}

def _day_ok(when, iso):
    """Covers muestra la fecha en hora del Este; se compara mes/día con el inicio del juego en ET (UTC−5)."""
    m = re.search(r"([A-Za-z]{3})\w*\.? (\d{1,2})", when or "")
    if not m or not iso: return True
    from datetime import datetime, timedelta
    try: dt = datetime.fromisoformat(iso.replace("Z", "+00:00")) - timedelta(hours=5)
    except Exception: return True
    return MON.get(m.group(1).lower()) == dt.month and int(m.group(2)) == dt.day

async def for_game(league, game):
    h, a = (game or {}).get("home") or {}, (game or {}).get("away") or {}
    for r in await rows(league):
        if _same(r["home"], h) and _same(r["away"], a) and _day_ok(r["when"], (game or {}).get("date")):
            n = (r["home"]["picks"] or 0) + (r["away"]["picks"] or 0)
            return dict(src="Covers Consensus", src_url=r["url"] or URL.format(slug=SLUG[league]), market="spread", n=n or None,
                        home=r["home"], away=r["away"], fetched=time.time(),
                        note="% de picks de los concursantes públicos de Covers contra el spread. Es opinión pública, no un modelo: úsalo como contexto.")
    return None

async def attach(r, league):
    try:
        c = await for_game(league, r.get("game"))
        if c: r["handicappers"] = c
    except Exception:
        pass
