"""E2E (Playwright + Chrome): buscador del Inicio y detalle de juego limpio (acordeones cerrados, mercados en bloques). API simulada.
uso: python3 tests/e2e_detalle.py <puerto> <ruta-chrome>"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
PORT, CHROME = sys.argv[1], sys.argv[2]
FX = os.path.join(os.path.dirname(__file__), "fixtures")
SOC = json.load(open(os.path.join(FX, "game_soc_mex1.json"))); NFL = json.load(open(os.path.join(FX, "game_nfl.json")))
def tm(i, n): return dict(id=f"{i}{n}", name=f"Equipo {i}{n}", short=f"E{i}{n}", abbr="E", logo=None, score="1", record="1-0", winner=False)
def lg(i): return dict(id=str(i), league="mex.1", league_name="Liga MX", sport="futbol", date="2026-11-03T20:00Z", state="in", status="1T", home=tm(i,1), away=tm(i,0), live=dict(text="1T 30'"), rec=[], prov={})
RES = dict(q="ro", leagues=[dict(key="mex.1", sport="futbol", name="Liga MX", emoji="⚽", n=9, sub=None)],
           teams=[dict(name="Roma", logo=None, league="ita.1", league_name="Serie A", sport="futbol", game_id="77", state="pre", date="2026-11-03T20:00Z", opp="Lazio")],
           games=[dict(id="77", league="ita.1", league_name="Serie A", sport="futbol", state="pre", status="", date="2026-11-03T20:00Z", home=dict(name="Roma", short="ROM", logo=None), away=dict(name="Lazio", short="LAZ", logo=None))])
async def main():
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, service_workers="block")
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.add_init_script("sessionStorage.setItem('splash_seen','1');const _si=window.setInterval;window.setInterval=(f,ms)=>_si(f,ms>=25000?400:ms);")
        jf = lambda body: (lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(body)))
        calls = {"search": [], "game": 0}
        def search(r):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(r.request.url).query).get("q", [""])[0]; calls["search"].append(q)
            body = dict(q=q, leagues=[], teams=[], games=[]) if q == "zzzz" else RES
            return r.fulfill(status=200, content_type="application/json", body=json.dumps(body))
        await pg.route("**/api/search*", search)
        await pg.route("**/api/home*", jf(dict(live=[lg(1), lg(2)], record={}, record_all={}, injuries=[], sports=[dict(key=k, today=1, live=0) for k in ("mlb","nfl","nba","nhl","tenis","futbol")], now=1.0)))
        await pg.route("**/api/picks*", jf(dict(items=[], n_games=0)))
        await pg.route("**/api/games*", jf(dict(ok=True,games=[],name="Liga MX",now=1.0,league="mex.1"))); await pg.route("**/api/img*", lambda r: r.fulfill(status=404, body="x"))
        # ---- buscador
        await pg.goto(f"http://localhost:{PORT}/#/"); await pg.wait_for_selector("#hm-search input")
        out["orden"] = await pg.evaluate("[...document.querySelectorAll('main section.hm, main div.snav')].map(e=>e.id)")
        out["input_font"] = await pg.evaluate("parseFloat(getComputedStyle(document.querySelector('#hm-search input')).fontSize)")
        out["oculto_al_inicio"] = await pg.evaluate("document.querySelector('.srch-r').hidden")
        await pg.type("#hm-search input", "roma", delay=40); await pg.wait_for_selector(".srch-r .sr"); await pg.wait_for_timeout(500)
        out["llamadas"] = list(calls["search"])                      # debounce: una sola petición para 'roma'
        out["grupos"] = await pg.evaluate("[...document.querySelectorAll('.srch-r .sr-h')].map(h=>h.innerText)")
        out["hrefs"] = await pg.evaluate("[...document.querySelectorAll('.srch-r a.sr')].map(a=>a.getAttribute('href'))")
        out["juego_home_first"] = await pg.evaluate("document.querySelector('.srch-r a.sr:last-child .sr-t').innerText.replace(/\\s+/g,' ')")
        await pg.fill("#hm-search input", "zzzz"); await pg.wait_for_function("document.querySelector('.sr-none')&&document.querySelector('.sr-none').innerText.includes('Sin resultados')")
        await pg.fill("#hm-search input", "r"); await pg.wait_for_timeout(500)
        out["corto_oculta"] = await pg.evaluate("document.querySelector('.srch-r').hidden")
        await pg.fill("#hm-search input", "roma"); await pg.wait_for_selector(".srch-r a.sr"); await pg.click(".srch-r a.sr >> nth=0"); await pg.wait_for_timeout(300)
        out["tap_liga"] = await pg.evaluate("location.hash")
        # ---- detalle futbol / nfl
        async def detalle(d, league, gid):
            await pg.route(f"**/api/game/{league}/{gid}*", jf(d))
            await pg.goto(f"http://localhost:{PORT}/#/juego/{league}/{gid}"); await pg.wait_for_selector(".mkc"); await pg.wait_for_timeout(400)
            return await pg.evaluate("""(()=>{const A=[...document.querySelectorAll('#app > .card')];
              return {top:A.map(c=>c.classList.contains('gh2')?'hero':c.classList.contains('mp')?'pick':c.classList.contains('mkc')?'mercados':c.classList.contains('acc')?'acc':(c.querySelector('h2')||{}).innerText||'?'),
              accs:[...document.querySelectorAll('#app > .acc')].map(c=>[c.querySelector('h2').innerText.trim(), c.classList.contains('closed')]),
              visibles_acc_body:[...document.querySelectorAll('#app > .acc.closed .acc-b')].filter(e=>e.offsetParent!==null).length,
              nombres:[...document.querySelectorAll('.gh2 .hs .n')].map(n=>n.innerText), bloques:[...document.querySelectorAll('.mkb-h')].map(h=>h.innerText),
              botones:[...document.querySelectorAll('.mkb')].map(m=>m.querySelectorAll('.ob').length), pick:[...document.querySelectorAll('.ob.pick .ol')].map(e=>e.innerText),
              notas_visibles:[...document.querySelectorAll('#app .note')].filter(e=>e.offsetParent!==null).length, picktxt:(document.querySelector(".mp-l")||{}).innerText||document.querySelector(".mp").outerHTML.slice(0,300),
              h:document.documentElement.scrollHeight, mid:(document.querySelector('.hmid')||{}).innerText}})()""")
        out["soc"] = await detalle(SOC, "mex.1", "401876909")
        out["nfl"] = await detalle(NFL, "nfl", "401873036")
        # ---- en vivo: se conserva el acordeón abierto y el scroll al refrescar
        live = json.loads(json.dumps(SOC)); live["game"]["state"] = "in"; live["game"]["status"] = "1T"; live["live"] = dict(text="1T 30'", stats=[], plays=[]); live["game"]["home"]["score"] = "1"; live["game"]["away"]["score"] = "0"
        n = {"v": 0}
        def lv(r):
            n["v"] += 1; return r.fulfill(status=200, content_type="application/json", body=json.dumps(live))
        await pg.route("**/api/game/mex.1/401876909*", lv)
        await pg.goto(f"http://localhost:{PORT}/#/juego/mex.1/401876909"); await pg.wait_for_selector(".mkc"); await pg.wait_for_timeout(300)
        out["en_vivo_abierto"] = await pg.evaluate("[...document.querySelectorAll('#app > .fold')].filter(c=>!c.classList.contains('closed')).map(c=>c.querySelector('h2').innerText.trim().slice(0,12))")
        out["marcador"] = await pg.evaluate("document.querySelector('.hm-sc').innerText.replace(/\\s+/g,' ')")
        await pg.click("#app > .acc >> nth=1 >> h2"); await pg.evaluate("window.scrollTo(0,150)"); before = n["v"]
        await pg.wait_for_function(f"true"); await pg.wait_for_timeout(1500)
        out["refrescos"] = n["v"] - before
        out["abierto_tras_refresco"] = await pg.evaluate("[...document.querySelectorAll('#app > .acc')].map(c=>!c.classList.contains('closed'))")
        out["scroll"] = await pg.evaluate("Math.round(scrollY)")
        out["errores"] = errs
        await b.close()
    print(json.dumps(out))
asyncio.run(main())
