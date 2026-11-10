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
        await pg.goto(f"http://localhost:{PORT}/#/inicio"); await pg.wait_for_selector("#hm-search input")
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
        # ---- detalle premium (futbol / nfl / tenis): secciones .ds en orden, sin acordeones ni bordes, ⓘ y plegado
        import sys as _s; _s.path.insert(0, os.path.join(os.path.dirname(__file__), "..")); _s.path.insert(0, os.path.dirname(__file__))
        import live_mocks as M
        async def detalle(d, league, gid):
            await pg.route(f"**/api/game/{league}/{gid}*", jf(d))
            await pg.goto(f"http://localhost:{PORT}/#/juego/{league}/{gid}"); await pg.wait_for_selector(".ds"); await pg.wait_for_timeout(400)
            return await pg.evaluate("""(()=>{const S=[...document.querySelectorAll('#app .ds')];
              return {keys:S.map(s=>s.dataset.k), accs:document.querySelectorAll('#app > .acc').length, hero:!!document.querySelector('#app .gh2, #app .hero, #app .card'),
              nombres:[...document.querySelectorAll('.gh2 .hs .n')].map(n=>n.innerText), bloques:[...document.querySelectorAll('.mkb-t')].map(h=>h.innerText),
              bordes:S.filter(s=>parseFloat(getComputedStyle(s).borderTopWidth)>0).length, h:document.documentElement.scrollHeight,
              heads:S.slice(0,3).map(s=>[getComputedStyle(s.querySelector('.ttl')).textTransform, parseFloat(getComputedStyle(s.querySelector('.ttl')).letterSpacing)>0])}})()""")
        ORDER = ["pred","rec","picks","prob","odds","mkt","cmp","pitch","trd","rcn","h2h","key","mdl","splits","rlm","move","lin","inj","wx","players"]
        out["soc"] = await detalle(M.with_pred(SOC), "mex.1", "401876909")
        out["nfl"] = await detalle(M.with_pred(NFL), "nfl", "401873036")
        out["tenis"] = await detalle(M.with_pred(M.tennis(state="pre")), "atp", "1")
        out["tenis_home_primero"] = await pg.evaluate("(()=>{const t=[...document.querySelectorAll('.pdtm small, .pdt, .gh2 .n')].map(e=>e.innerText);return t.slice(0,2)})()")
        out["orden_ok"] = {k: [x for x in out[k]["keys"] if x in ORDER] == sorted([x for x in out[k]["keys"] if x in ORDER], key=ORDER.index) for k in ("soc", "nfl")}
        # ⓘ abre/cierra la nota y plegar con el título; el estado sobrevive al cambio de pestaña interna
        await pg.goto(f"http://localhost:{PORT}/#/juego/nfl/401873036"); await pg.wait_for_selector(".ds[data-k=pred] .ib"); await pg.wait_for_timeout(300)
        out["info_oculta"] = await pg.evaluate("document.querySelector('.ds[data-k=pred] .di').hidden")
        await pg.click(".ds[data-k=pred] .ib"); out["info_abierta"] = await pg.evaluate("!document.querySelector('.ds[data-k=pred] .di').hidden")
        await pg.click(".ds[data-k=pred] .ttl"); out["plegada"] = await pg.evaluate("document.querySelector('.ds[data-k=pred]').classList.contains('shut')")
        await pg.click(".ds[data-k=pred] .ttl"); await pg.click(".ds[data-k=pred] .ib")            # se despliega y se oculta la nota otra vez
        out["pred_rows"] = await pg.evaluate("[...document.querySelectorAll('.ds[data-k=pred] .pdr')].filter(e=>e.offsetParent!==null).length")
        # fútbol: filas de predicción en lista compacta con las líneas del modelo y córners
        await pg.goto(f"http://localhost:{PORT}/#/juego/mex.1/401876909"); await pg.wait_for_selector(".ds[data-k=pred] .pdr"); await pg.wait_for_timeout(300)
        out["pred_soc"] = await pg.evaluate("[...document.querySelectorAll('.ds[data-k=pred] .pdr small')].map(e=>e.innerText.trim())")
        out["pred_resumen"] = await pg.evaluate("[...document.querySelectorAll('.ds[data-k=pred] .pdsm span')].map(e=>e.innerText.trim())")
        # ---- en vivo: cancha en vivo arriba y el estado (ⓘ, plegado, scroll) sobrevive al refresco de 25 s
        live = M.soccer(); n = {"v": 0}
        def lv(r):
            n["v"] += 1; return r.fulfill(status=200, content_type="application/json", body=json.dumps(live))
        await pg.route("**/api/game/mex.1/401876909*", lv)
        await pg.goto(f"http://localhost:{PORT}/#/juego/nfl/401873036"); await pg.wait_for_timeout(300)          # otra ruta para forzar la recarga del mismo juego
        await pg.goto(f"http://localhost:{PORT}/#/juego/mex.1/401876909"); await pg.wait_for_selector(".cvw"); await pg.wait_for_timeout(300)
        out["cancha_arriba"] = await pg.evaluate("[...document.querySelectorAll('#app > *')].findIndex(e=>e.classList.contains('cvw')||e.querySelector('.cvw'))")
        out["marcador"] = await pg.evaluate("document.querySelector('.cvsc').innerText.replace(/\\s+/g,' ')")
        k0 = await pg.evaluate("document.querySelector('.ds .ib')&&document.querySelector('.ds .ib').closest('.ds').dataset.k")
        if k0:
            await pg.click(f".ds[data-k={k0}] .ib"); await pg.click(f".ds[data-k={k0}] .ttl")
        await pg.evaluate("window.scrollTo(0,150)"); before = n["v"]
        await pg.wait_for_timeout(1600)
        out["refrescos"] = n["v"] - before
        out["estado_tras_refresco"] = await pg.evaluate("(k=>{const s=document.querySelector('.ds[data-k='+k+']');return s?[s.classList.contains('shut'),!s.querySelector('.di').hidden]:null})(%s)" % json.dumps(k0))
        out["scroll"] = await pg.evaluate("Math.round(scrollY)")
        out["errores"] = errs
        await b.close()
    print(json.dumps(out))
asyncio.run(main())
