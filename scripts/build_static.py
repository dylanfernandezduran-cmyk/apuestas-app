"""Construye el sitio ESTÁTICO de NRNM para GitHub Pages (pt90u): corre el mismo backend en proceso (sin servidor),
consulta los mismos endpoints que usa la app y guarda cada respuesta como JSON en site/data/. El frontend, al detectar
window.NRNM_STATIC, lee esos archivos en lugar de /api. Datos reales de las mismas fuentes; nada se inventa.

uso: python scripts/build_static.py [carpeta_salida=site] [horas_adelante=48]
La base SQLite (picks, líneas de apertura/cierre, récord, predicciones) se toma de APUESTAS_DB (el workflow la conserva en la rama `estado`)."""
import asyncio, json, os, re, shutil, sys, time
from datetime import datetime, timedelta, timezone
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "site"))
HOURS = float(sys.argv[2]) if len(sys.argv) > 2 else 48
import httpx
from server import main, data
from server.config import LEAGUES

def key_for(path):
    """MISMA regla que staticUrl() en static/app.js: /api/x/y?b=2&a=1 -> data/x/y@a=1_b=2.json"""
    p, _, q = path.partition("?")
    p = p[len("/api/"):] if p.startswith("/api/") else p.lstrip("/")
    if q:
        q = "&".join(sorted(x for x in q.split("&") if x))
        p += "@" + re.sub(r"[^A-Za-z0-9._-]", "_", q)
    return "data/" + p + ".json"

STATS = dict(ok=0, err=0, files=0, errors=[])

async def main_():
    t0 = time.time()
    if os.path.isdir(OUT): shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(ROOT, "static"), os.path.join(OUT, "static"))
    tr = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=tr, base_url="http://nrnm", timeout=180) as c:
        sem = asyncio.Semaphore(6)
        async def get(path, save=True):
            async with sem:
                try: r = await c.get(path)
                except Exception as e:
                    STATS["err"] += 1; STATS["errors"].append(f"{path}: {type(e).__name__}"); return None
            if r.status_code != 200:
                STATS["err"] += 1; STATS["errors"].append(f"{path}: HTTP {r.status_code}"); return None
            STATS["ok"] += 1
            if save:
                fn = os.path.join(OUT, key_for(path)); os.makedirs(os.path.dirname(fn), exist_ok=True)
                open(fn, "wb").write(r.content); STATS["files"] += 1
            return r
        # 1) calificar lo pendiente primero (récord al día)
        try: await c.post("/api/grade")
        except Exception: pass
        # 2) índice, manifest
        r = await get("/", save=False)
        html = r.text if r else open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8").read()
        html = html.replace('"/static/', '"static/').replace('"/manifest.webmanifest"', '"manifest.webmanifest"')
        built = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        html = html.replace("<head>", f"<head><script>window.NRNM_STATIC={{built:'{built}'}};</script>", 1)
        open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
        m = await get("/manifest.webmanifest", save=False)
        if m:
            mf = m.json(); mf["start_url"] = "./"; mf["scope"] = "./"
            for ic in mf.get("icons", []): ic["src"] = ic["src"].lstrip("/")
            json.dump(mf, open(os.path.join(OUT, "manifest.webmanifest"), "w"))
        # 3) listas por liga
        sports = (await get("/api/sports")).json()
        leagues = [l["key"] for s in sports for l in s["leagues"]]
        lists = await asyncio.gather(*[get(f"/api/games?league={l}") for l in leagues])
        await asyncio.gather(*[get(f"/api/league_wx?league={l}") for l in leagues], *[get(f"/api/league_brief?league={l}") for l in leagues])
        # 4) detalle de cada juego relevante (en vivo, próximas HOURS h, terminados de hoy) + props de jugadores
        now = datetime.now(timezone.utc); lim = now + timedelta(hours=HOURS); since = now - timedelta(hours=20)
        jobs = []
        for l, r in zip(leagues, lists):
            if not r: continue
            for g in r.json().get("games", []):
                d = data.parse_dt(g.get("date"))
                if g["state"] == "in" or (d and since <= d <= lim):
                    jobs.append((l, g))
        await asyncio.gather(*[get(f"/api/game/{l}/{g['id']}") for l, g in jobs])
        await asyncio.gather(*[get(f"/api/props/{l}/{g['id']}") for l, g in jobs
                               if LEAGUES[l]["family"] != "tennis" and g["state"] != "post" and (data.parse_dt(g.get("date")) or now) <= now + timedelta(hours=30)])
        # 5) resúmenes (después de analizar: picks registrados/actualizados en este ciclo)
        for sc in ("24h", "hoy", "manana", "72h"): await get(f"/api/picks?scope={sc}")
        await get("/api/home"); await get("/api/record?limit=80")
        await get("/api/chat/status")
    meta = dict(built=built, seconds=round(time.time() - t0, 1), games=len(jobs), ok=STATS["ok"], err=STATS["err"], errors=STATS["errors"][:40])
    json.dump(meta, open(os.path.join(OUT, "data", "build.json"), "w"), indent=1)
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print(json.dumps(meta, indent=1))

if __name__ == "__main__":
    asyncio.run(main_())
