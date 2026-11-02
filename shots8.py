import asyncio, json, urllib.request, sys
from playwright.async_api import async_playwright
B="http://localhost:8766"
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
        ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,locale="es-MX",timezone_id="America/Mexico_City",has_touch=True,is_mobile=True)
        await ctx.add_init_script("try{sessionStorage.setItem('splash_seen','1')}catch(e){}")
        pg=await ctx.new_page(); errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
        async def go(h,w="Actualizado"):
            await pg.goto(B+"/"+h); await pg.wait_for_function("!document.querySelector('.loading')",timeout=90000)
            await pg.wait_for_function(f"document.body.innerText.includes({w!r})",timeout=60000); await pg.wait_for_timeout(2000)
        async def full(path,y=0,h=1700):
            vw=await pg.evaluate("document.documentElement.clientWidth"); await pg.screenshot(path=path,full_page=True,clip={"x":0,"y":y,"width":vw,"height":h})
        await go("#/","Récord"); await full("screens/mobile_70_nrnm_home.png",0,1800)
        await go(sys.argv[1] if len(sys.argv)>1 else "#/deporte/nba/nba"); await full("screens/mobile_70_nrnm_lista.png",0,1700)
        print("errs",errs); await b.close()
asyncio.run(main())
