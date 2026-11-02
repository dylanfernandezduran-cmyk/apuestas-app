#!/usr/bin/env python3
"""Hoja de presentación de marcas + maqueta de ícono en pantalla de inicio de iPhone.
Uso: python3 scripts/make_brand_sheet.py avizor atalaya zahori lince [--sheet screens/logos_ojo_options.png] [--prefix logo_ojo_]
Requiere playwright + google-chrome. Lee static/brand/brand.json y static/brand/<opcion>/{glyph.svg,icons/}."""
import json, os, sys, base64, html
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
B = os.path.join(ROOT, "static", "brand"); S = os.path.join(ROOT, "screens"); os.makedirs(S, exist_ok=True)
a = sys.argv[1:]
def opt(n, d): return a[a.index(n) + 1] if n in a else d
sheet = opt("--sheet", os.path.join(S, "logos_ojo_options.png")); prefix = opt("--prefix", "logo_ojo_")
names = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or not a[i - 1].startswith("--"))]
cfg = json.load(open(os.path.join(B, "brand.json"), encoding="utf-8")); bg = cfg["theme"]["bg"]
def glyph(k): return open(os.path.join(B, k, "glyph.svg"), encoding="utf-8").read()
def b64(k, f): return "data:image/png;base64," + base64.b64encode(open(os.path.join(B, k, "icons", f), "rb").read()).decode()
cards = ""
for k in names:
    o = cfg["options"][k]; g = glyph(k)
    cards += f'''<section class="opt"><div class="big">{g}</div><div class="nm">{o["name"]}</div><div class="tg">{html.escape(o["tagline"])}</div>
<div class="row"><div class="ic"><img src="{b64(k, "apple-touch-icon.png")}"><small>icono 180</small></div><div class="ic"><img class="s32" src="{b64(k, "favicon-32.png")}"><small>32 px</small></div>
<div class="ic"><span class="s16">{g}</span><small>16 px</small></div></div><p>{html.escape(o["desc"])}</p></section>'''
css = f'''*{{box-sizing:border-box}}body{{margin:0;background:{bg};color:#e6ebf2;font:15px/1.5 -apple-system,system-ui,Segoe UI,Roboto,sans-serif;padding:32px 28px}}
h1{{font-size:22px;margin:0 0 4px}}.sub{{color:#8b95a7;margin:0 0 22px;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat({min(len(names),4)},1fr);gap:16px}}.opt{{background:#121722;border:1px solid #1f2735;border-radius:16px;padding:22px 18px}}
.big{{width:150px;height:150px;margin:0 auto 14px;background:{bg};border-radius:32px;padding:20px;border:1px solid #1f2735}}.big svg,.s16 svg{{width:100%;height:100%;display:block}}
.nm{{font-size:24px;font-weight:700;text-align:center}}.tg{{color:#34d399;text-align:center;margin-bottom:16px;font-size:13px}}
.row{{display:flex;align-items:flex-end;gap:14px;justify-content:center;margin:6px 0 14px}}.ic{{display:flex;flex-direction:column;align-items:center;gap:6px}}.ic small{{color:#6b7587;font-size:10.5px}}
.ic img:not(.s32){{width:60px;height:60px;border-radius:13.4px}}.s32{{width:32px;height:32px}}.s16{{display:inline-block;width:16px;height:16px;margin-bottom:8px}}
p{{color:#aab3c2;font-size:12.5px;margin:0}}'''
doc = f'<!doctype html><meta charset="utf-8"><style>{css}</style><h1>Ojo que todo lo ve · {len(names)} opciones</h1><p class="sub">Minimalista, fondo oscuro, un solo acento verde. Se ven igual de claras a 180 px, 32 px y 16 px.</p><div class="grid">{cards}</div>'
def phone(k):
    o = cfg["options"][k]; ph = ["Mapas", "Notas", "Clima", "Fotos", "Reloj", "Cámara", "Correo", "Agenda", "Música", "Archivos", "Ajustes", "Salud", "Billetera", "Libros", "Brújula", "Tienda", "Teléfono", "Mensajes", "Contactos", "Podcasts", "Calculadora", "Voz", "Safari", "Atajos", "Wallet", "Casa"]
    hues = [212, 28, 190, 330, 250, 160, 12, 280, 350, 45, 220, 140, 200, 20, 100, 205, 120, 300, 40, 260, 170, 10, 230, 60, 320, 150, 80]
    cells = []
    for i in range(20):
        if i == 6:
            cells.append(f'<div class="app"><img class="mine" src="{b64(k, "apple-touch-icon.png")}"><span>{o["name"]}</span></div>')
        else:
            j = i - (1 if i > 6 else 0)
            cells.append(f'<div class="app"><div class="ph" style="background:hsl({hues[j]} 28% 30%)"></div><span>{ph[j]}</span></div>')
    dock = "".join(f'<div class="ph d" style="background:hsl({h} 30% 32%)"></div>' for h in (150, 210, 30, 280))
    return f'''<!doctype html><meta charset="utf-8"><style>*{{box-sizing:border-box}}body{{margin:0;width:390px;height:844px;overflow:hidden;font-family:-apple-system,system-ui,Segoe UI,Roboto,sans-serif;color:#fff;
background:radial-gradient(120% 70% at 30% 0%,#1d3b3a 0%,#0e1a24 45%,#070b10 100%);position:relative}}
.sb{{display:flex;justify-content:space-between;padding:14px 30px 0;font-weight:600;font-size:15px}}.sb i{{width:60px;height:14px;border:1.5px solid #fff;border-radius:4px;opacity:.85}}
.grid{{display:grid;grid-template-columns:repeat(4,60px);justify-content:space-between;padding:34px 27px 0;row-gap:26px}}
.app{{display:flex;flex-direction:column;align-items:center;gap:6px}}.app span{{font-size:11px;text-shadow:0 1px 2px rgba(0,0,0,.5)}}
.ph{{width:60px;height:60px;border-radius:13.4px;opacity:.9}}.mine{{width:60px;height:60px;border-radius:13.4px;box-shadow:0 0 0 .5px rgba(255,255,255,.18)}}
.dock{{position:absolute;left:14px;right:14px;bottom:18px;height:92px;border-radius:30px;background:rgba(255,255,255,.14);backdrop-filter:blur(20px);display:flex;justify-content:space-around;align-items:center;padding:0 10px}}
.d{{opacity:.95}}.srch{{position:absolute;left:0;right:0;bottom:122px;text-align:center}}.srch b{{display:inline-block;padding:6px 40px;border-radius:14px;background:rgba(255,255,255,.14);font-size:12px;font-weight:500;opacity:.9}}
.home{{position:absolute;left:50%;bottom:7px;width:134px;height:5px;margin-left:-67px;border-radius:3px;background:#fff;opacity:.9}}</style>
<div class="sb"><span>9:41</span><i></i></div><div class="grid">{"".join(cells)}</div><div class="srch"><b>Buscar</b></div><div class="dock">{dock}</div><div class="home"></div>'''
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = br.new_page(viewport={"width": 280 * len(names) + 64 if len(names) < 4 else 1240, "height": 560}, device_scale_factor=2)
    pg.set_content(doc); pg.wait_for_timeout(300); pg.screenshot(path=sheet, full_page=True); pg.close()
    for k in names:
        pg = br.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        pg.set_content(phone(k)); pg.wait_for_timeout(200); pg.screenshot(path=os.path.join(S, f"{prefix}{k}.png")); pg.close()
    br.close()
print("ok", sheet)
