"""E2E (Playwright + Chrome): orden del Inicio (en vivo, deportes, picks; sin Récord ni Bajas) y Picks agrupados por deporte. API simulada.
uso: python3 tests/e2e_layout.py <puerto> <ruta-chrome>"""
import asyncio, json, sys
from playwright.async_api import async_playwright
PORT, CHROME = sys.argv[1], sys.argv[2]
SP = [("mlb","MLB"),("nfl","NFL"),("nba","NBA"),("nhl","NHL"),("tenis","Tenis"),("futbol","Fútbol")]
def team(i, n): return dict(id=f"{i}{n}", name=f"Equipo {i}{n}", short=f"E{i}{n}", abbr="E", logo=None, score="1", record="1-0", winner=False)
def game(i, sport, state="in"):
    return dict(id=str(i), league={"tenis":"atp","futbol":"mex.1"}.get(sport, sport), league_name=sport.upper(), sport=sport, date="2026-11-03T20:00Z", state=state, status="Q2", home=team(i,1), away=team(i,0), live=dict(text="Q2"), rec=[], prov={})
def item(i, sport, status="PICK"):
    return dict(game=game(i, sport, "pre"), status=status, confidence="media", has_odds=True, brief=[],
                lean=dict(label=f"Pick {sport} {i}", price_txt="-110", edge=3.0, p_model=.55, p_nv=.5, fair_txt="-120", max_txt="-115", signals=None))
async def main():
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, service_workers="block")
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.add_init_script("sessionStorage.setItem('splash_seen','1')")
        jf = lambda body: (lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(body)))
        home = dict(live=[game(1,"nba"), game(2,"mlb")], record=dict(graded=3, W=2, L=1, P=0), record_all=dict(graded=3), injuries=[dict(league="nba", id="1", name="X", pos="G", team="T", detail="out", n_out=1)],
                    sports=[dict(key=k, today=2, live=1 if k == "nba" else 0) for k, _ in SP], now=1.0)
        await pg.route("**/api/home*", jf(home))
        mixed = [item(10,"tenis"), item(11,"nhl"), item(12,"futbol"), item(13,"nba"), item(14,"mlb"), item(15,"nfl"), item(16,"futbol"), item(17,"mlb")]
        await pg.route("**/api/picks*", jf(dict(items=mixed, n_games=8)))
        await pg.route("**/api/img*", lambda r: r.fulfill(status=404, body="x"))
        await pg.goto(f"http://localhost:{PORT}/#/"); await pg.wait_for_selector(".snav a"); await pg.wait_for_selector("#hm-picks a.pk")
        out["secciones"] = await pg.evaluate("[...document.querySelectorAll('main section.hm, main div.snav')].map(e=>e.id)")
        out["texto_inicio_tiene"] = await pg.evaluate("['Récord ·','Bajas confirmadas'].filter(t=>document.querySelector('main').innerText.includes(t))")
        out["nav"] = await pg.evaluate("[...document.querySelectorAll('.snav a')].map(a=>a.innerText.replace(/\\s+/g,' ').trim())")
        out["nav_href"] = await pg.evaluate("[...document.querySelectorAll('.snav a')].map(a=>a.getAttribute('href'))")
        out["nav_estilo"] = await pg.evaluate("(()=>{const a=getComputedStyle(document.querySelector('.snav a'));return {bw:a.borderTopWidth,bg:a.backgroundColor,sh:a.boxShadow}})()")
        out["nav_vivo"] = await pg.evaluate("[...document.querySelectorAll('.snav a.lv')].map(a=>a.dataset.sp)")
        out["rec_tab"] = await pg.evaluate("!!document.querySelector('nav a[href=\"#/record\"], header a[href=\"#/record\"]')")
        await pg.click(".snav a[data-sp='nfl']"); await pg.wait_for_timeout(500)
        out["tap_nfl"] = await pg.evaluate("location.hash")
        await pg.goto(f"http://localhost:{PORT}/#/picks/hoy"); await pg.wait_for_selector(".pgrp")
        out["grupos"] = await pg.evaluate("[...document.querySelectorAll('.pgrp')].map(h=>h.dataset.sport)")
        out["orden_cards"] = await pg.evaluate("[...document.querySelectorAll('main .pgrp, main .card.pk')].map(e=>e.classList.contains('pgrp')?'H:'+e.dataset.sport:'c').join(',')")
        await pg.route("**/api/picks*", jf(dict(items=[item(1,"nba"), item(2,"mlb")], n_games=2)))
        await pg.goto(f"http://localhost:{PORT}/#/picks/72h"); await pg.wait_for_selector(".pgrp")
        out["grupos_sin_vacios"] = await pg.evaluate("[...document.querySelectorAll('.pgrp')].map(h=>h.dataset.sport)")
        out["errores"] = errs
        await b.close()
    print(json.dumps(out))
asyncio.run(main())
