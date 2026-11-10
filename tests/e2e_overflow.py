"""E2E (Playwright + Chrome emulando iPhone): ningún elemento del detalle se sale del viewport a 375/390/430 px. API simulada.
uso: python3 tests/e2e_overflow.py <puerto> <ruta-chrome>  -> JSON {ancho: [problemas]}
Nota: WebKit no está disponible en la caja; se emula el viewport/touch de iPhone con Chromium."""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
PORT, CHROME = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import live_mocks as M
FX = os.path.join(HERE, "fixtures")
SOC = json.load(open(os.path.join(FX, "game_soc_mex1.json"))); NFL = json.load(open(os.path.join(FX, "game_nfl.json")))
CASES = [("mex.1", "401876909", M.with_pred(SOC)), ("nfl", "401873036", M.with_pred(NFL)), ("atp", "1", M.with_pred(M.tennis(state="pre"))),
         ("mex.1", "401876909", M.soccer()), ("atp", "1", M.tennis()), ("nfl", "401873036", M.nfl()), ("mlb", "1", M.mlb()), ("nba", "1", M.nba()), ("nhl", "1", M.nhl())]
AUDIT = """(()=>{
  const vw=document.documentElement.clientWidth, bad=[];
  const clipped=el=>{for(let p=el.parentElement;p&&p!==document.body;p=p.parentElement){const o=getComputedStyle(p);if(o.overflowX!=='visible'&&p.getBoundingClientRect().right<=vw+1&&p.getBoundingClientRect().left>=-1)return true}return false};
  for(const el of document.querySelectorAll('#app *')){
    if(el.closest('svg')&&el.tagName.toLowerCase()!=='svg')continue;
    const cs=getComputedStyle(el); if(cs.display==='none'||cs.visibility==='hidden')continue;
    const r=el.getBoundingClientRect(); if(!r.width&&!r.height)continue;
    if((r.left<-1||r.right>vw+1)&&!clipped(el)) bad.push((el.className&&el.className.baseVal===undefined?el.className:el.tagName)+' '+Math.round(r.left)+'..'+Math.round(r.right)+' "'+(el.innerText||'').slice(0,30).replace(/\\s+/g,' ')+'"');
  }
  if(document.documentElement.scrollWidth>vw+1) bad.push('SCROLL-X '+document.documentElement.scrollWidth+'>'+vw);
  // el texto de cada tarjeta/sección debe quedar dentro de su contenedor
  for(const s of document.querySelectorAll('#app .ds, #app .card')){const sr=s.getBoundingClientRect();
    for(const el of s.querySelectorAll('*')){const r=el.getBoundingClientRect(); if(!r.width||getComputedStyle(el).display==='none')continue; if(el.closest('svg')||el.closest('.stad'))continue;
      if(!clipped(el)&&(r.left<sr.left-1||r.right>sr.right+1)) bad.push('FUERA-DE-TARJETA '+(typeof el.className==='string'?el.className:el.tagName)+' '+Math.round(r.left)+'..'+Math.round(r.right)+' vs '+Math.round(sr.left)+'..'+Math.round(sr.right));}}
  // texto desbordado: los rectángulos reales del texto (Range) también deben quedar dentro del viewport y de su tarjeta
  const w=document.createTreeWalker(document.getElementById('app'),NodeFilter.SHOW_TEXT);
  for(let n;n=w.nextNode();){ if(!n.textContent.trim())continue; const el=n.parentElement; if(!el||el.closest('svg')||getComputedStyle(el).display==='none')continue;
    const rg=document.createRange(); rg.selectNodeContents(n); const host=el.closest('.ds,.card'); const hr=host?host.getBoundingClientRect():null;
    for(const r of rg.getClientRects()){ if(!r.width)continue; if(clipped(el))continue;
      if(r.left<-1||r.right>vw+1||(hr&&(r.left<hr.left-1||r.right>hr.right+1))){ bad.push('TEXTO-FUERA '+(typeof el.className==='string'?el.className:el.tagName)+' "'+n.textContent.trim().slice(0,28)+'" '+Math.round(r.left)+'..'+Math.round(r.right)); break; } } }
  return [...new Set(bad)].slice(0,12);})()"""
async def main():
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        for w in (375, 390, 430):
            ctx = await b.new_context(viewport={"width": w, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2, service_workers="block")
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.add_init_script("sessionStorage.setItem('splash_seen','1')")
            await pg.route("**/api/img*", lambda r: r.fulfill(status=404, body="x"))
            probs = []
            for i, (lg, gid, d) in enumerate(CASES):
                await pg.goto(f"http://localhost:{PORT}/#/inicio"); await pg.wait_for_timeout(100)
                await pg.route(f"**/api/game/{lg}/{gid}*", (lambda body: (lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(body))))(d))
                await pg.goto(f"http://localhost:{PORT}/#/juego/{lg}/{gid}"); await pg.wait_for_selector(".ds, .cvw", timeout=15000); await pg.wait_for_timeout(500)
                # desplegar todas las notas ⓘ para auditarlas también
                await pg.evaluate("document.querySelectorAll('.ds .ib').forEach(b=>{if(!b.classList.contains('on'))b.click()})"); await pg.wait_for_timeout(200)
                for x in await pg.evaluate(AUDIT): probs.append(f"[{i}:{lg}] {x}")
            for rl in sys.argv[3:]:                                         # juegos REALES del servidor (sin simular), p. ej. mex.1/401876910
                lg, gid = rl.split("/")
                await pg.goto(f"http://localhost:{PORT}/#/inicio"); await pg.wait_for_timeout(100)
                await pg.goto(f"http://localhost:{PORT}/#/juego/{lg}/{gid}"); await pg.wait_for_selector(".ds", timeout=90000); await pg.wait_for_timeout(1500)
                try: await pg.wait_for_function("!document.querySelector('.pp-host') || !document.querySelector('.pp-host').innerText.includes('Cargando')", timeout=60000)   # props de jugadores (carga asíncrona)
                except Exception: pass
                await pg.evaluate("document.querySelectorAll('.ds .ib').forEach(b=>{if(!b.classList.contains('on'))b.click()})"); await pg.wait_for_timeout(200)
                for x in await pg.evaluate(AUDIT): probs.append(f"[real:{rl}] {x}")
                if await pg.query_selector(".pp-row"):                      # pantalla de un prop (barras, filtros, lista de juegos) en 5/10/20 juegos, más/menos y línea por juego
                    await pg.click(".pp-row"); await pg.wait_for_selector(".pp-bar", timeout=60000); await pg.wait_for_timeout(500)
                    for sel in (None, '[data-sd=under]', '[data-n="20"]', '[data-md=hist]', '[data-n="5"]'):
                        if sel and await pg.query_selector(".pp-fil " + sel): await pg.click(".pp-fil " + sel); await pg.wait_for_timeout(2500 if sel == '[data-n="20"]' else 300)
                        for x in await pg.evaluate(AUDIT): probs.append(f"[prop:{rl}:{sel}] {x}")
            out[w] = probs + (["JS " + e for e in errs])
        await b.close()
    print(json.dumps(out))
asyncio.run(main())
