"""E2E (Playwright + Chrome) del carrusel de juegos en vivo con /api/home simulado. Lo lanza tests/test_logos_carrusel.py; imprime JSON con los resultados.
uso: python3 tests/e2e_carrusel.py <puerto> <ruta-chrome>"""
import asyncio, json, sys
from playwright.async_api import async_playwright
PORT, CHROME = sys.argv[1], sys.argv[2]

def game(i, score):
    t = lambda n, s: dict(id=str(i * 10 + n), name=f"Equipo {i}{'AB'[n]}", short=f"E{i}{'AB'[n]}", abbr=f"E{i}", logo=None if n else "https://a.espncdn.com/i/teamlogos/nba/500/bos.png", score=str(s), record="1-0", winner=False)
    return dict(id=str(i), league="nba", league_name="NBA", sport="nba", date="2026-11-02T20:00Z", state="in", status="Q2 5:00", home=t(1, score), away=t(0, 3), live=dict(text="Q2 5:00"), rec=[], prov={})

async def main():
    out = {}
    calls = {"n": 0}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, service_workers="block")   # el SW saltaría page.route
        pg = await ctx.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.add_init_script("sessionStorage.setItem('splash_seen','1');const _si=window.setInterval;window.setInterval=(f,ms)=>_si(f,ms>=25000?400:ms);")
        async def home(route):
            calls["n"] += 1
            sc = 10 * calls["n"]
            body = dict(live=[game(i, sc) for i in range(1, 6)], record=dict(graded=0), record_all=dict(graded=0), injuries=[], sports=[], now=1.0)
            await route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
        await pg.route("**/api/home*", home)
        await pg.route("**/api/picks*", lambda r: r.fulfill(status=200, content_type="application/json", body='{"items":[]}'))
        await pg.route("**/api/img*", lambda r: r.fulfill(status=404, body="x"))      # imagen rota -> iniciales
        await pg.goto(f"http://localhost:{PORT}/#/")
        await pg.wait_for_selector(".car-slide")
        st = "({n:document.querySelectorAll('.car-slide').length,dots:document.querySelectorAll('.car-dots button').length,txt:document.querySelector('.car-n').textContent,on:[...document.querySelectorAll('.car-dots button')].findIndex(x=>x.classList.contains('on')),w:document.querySelector('.car-track').clientWidth,vis:getComputedStyle(document.querySelector('.car-track')).scrollSnapType})"
        out["inicio"] = await pg.evaluate(st)
        await pg.click(".car-dots button:nth-child(3)"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.querySelector('.car-track').scrollBy({left:document.querySelector('.car-track').clientWidth,behavior:'instant'})"); await pg.wait_for_timeout(300)
        out["tras_deslizar"] = await pg.evaluate(st)
        n0 = calls["n"]
        score0 = await pg.evaluate("document.querySelectorAll('.car-slide')[3].querySelectorAll('.lr-t .sc')[1].textContent")
        for _ in range(40):
            if calls["n"] >= n0 + 2: break
            await pg.wait_for_timeout(250)
        await pg.wait_for_timeout(300)
        out["tras_refresco"] = await pg.evaluate(st)
        out["marcador_antes"] = score0
        out["marcador_despues"] = await pg.evaluate("document.querySelectorAll('.car-slide')[3].querySelectorAll('.lr-t .sc')[1].textContent")
        out["iniciales"] = await pg.evaluate("document.querySelectorAll('.car-slide .tl.ini').length")
        out["errores"] = errs
        await b.close()
    print(json.dumps(out))
asyncio.run(main())
