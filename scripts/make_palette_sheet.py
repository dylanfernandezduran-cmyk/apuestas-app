#!/usr/bin/env python3
"""Hoja de paleta NRNM: swatches + roles + contraste WCAG + colorways del logo (grande, ícono 180, 32 px, 16 px)."""
import os, base64, html
from playwright.sync_api import sync_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); B = os.path.join(ROOT, "static/brand")
BG, PANEL, TX, MUT = "#0b0e13", "#11161d", "#e6ebf2", "#7f8b9c"
SW = [("Rosa", "#FF1179", "Marca · CTA · pick", "foto rosa (mediana de todo el recuadro)"), ("Teal", "#06AAC4", "Ganado · positivo · edge", "jersey Hornets (mediana, sin números ni blancos)"),
      ("Azul", "#3C85F7", "En vivo · info · enlaces", "Porsche 911 GT3 RS, carrocería (mediana)"), ("Pérdida (= rosa)", "#FF1179", "Perdido · baja · error (rosa)", "igual que el rosa de marca"),
      ("Ámbar", "#fbbf24", "Aviso · lean · probable", "ya existía"), ("Fondo", BG, "Fondo", ""), ("Panel", PANEL, "Tarjetas", ""), ("Texto", TX, "Texto", ""), ("Texto 2", MUT, "Secundario", "")]
def lum(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]; c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]; return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
def cr(a, b): la, lb = sorted((lum(a), lum(b)), reverse=True); return (la + .05) / (lb + .05)
def b64(k, f): return "data:image/png;base64," + base64.b64encode(open(f"{B}/{k}/icons/{f}", "rb").read()).decode()
CW = [("nrnm", "1 · Rosa neón (recomendada)", "triángulo rosa · ojo blanco · pelota teal"), ("nrnm_degradado", "2 · Degradado rosa→azul", "triángulo degradado sutil · pelota rosa"), ("nrnm_azul", "3 · Azul + teal", "triángulo azul · base y pelota teal")]
sw = "".join(f'<div class="sw"><div class="c" style="background:{h}"><b style="color:{"#0b0e13" if lum(h)>.18 else "#e6ebf2"}">{h}</b></div><div class="t"><b>{n}</b><span>{r}</span><i>{s}</i></div></div>' for n, h, r, s in SW)
rows = "".join(f'<tr><td><span class="dot" style="background:{h}"></span>{n}</td><td>{h}</td><td>{cr(h, BG):.2f}</td><td>{cr(h, PANEL):.2f}</td><td>{"AA ✓" if cr(h, PANEL) >= 4.5 else "solo grande"}</td><td>{cr(BG, h):.2f}</td></tr>' for n, h in [("Rosa", "#FF1179"), ("Teal", "#06AAC4"), ("Azul", "#3C85F7"), ("Pérdida (= rosa)", "#FF1179"), ("Ámbar", "#fbbf24"), ("Texto 2", MUT)])
cws = ""
for k, t, d in CW:
    g = open(f"{B}/{k}/glyph.svg").read()
    cws += f'<div class="cw"><div class="big">{g}</div><h4>{t}</h4><p>{d}</p><div class="row"><div><img class="i180" src="{b64(k, "apple-touch-icon.png")}"><small>180</small></div><div><img class="i32" src="{b64(k, "favicon-32.png")}"><small>32</small></div><div><span class="i16">{g}</span><small>16</small></div><div class="lk"><span class="lm">{g}</span><b>NRNM</b></div></div></div>'
chips = '<span class="ch" style="--c:255,17,121;color:#FF1179">PICK</span><span class="ch" style="--c:6,170,196;color:#06AAC4">+7.3pp edge · GANADO</span><span class="ch" style="--c:60,133,247;color:#3C85F7">● EN VIVO · Set 3</span><span class="ch" style="--c:255,17,121;color:#FF1179">PERDIDO · 7 bajas</span><span class="ch" style="--c:251,191,36;color:#fbbf24">LEAN</span><span class="btn">Ver todos →</span>'
css = f'''*{{box-sizing:border-box}}body{{margin:0;background:{BG};color:{TX};font:14px/1.45 -apple-system,Inter,system-ui,"Segoe UI",sans-serif;padding:34px 36px;width:1280px}}
h1{{font-size:24px;margin:0 0 4px}}.sub{{color:{MUT};margin:0 0 22px}}h3{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:{MUT};margin:26px 0 12px}}
.sws{{display:grid;grid-template-columns:repeat(9,1fr);gap:10px}}.sw .c{{height:90px;border-radius:12px;display:flex;align-items:flex-end;padding:8px;border:1px solid #1f2735}}.sw .c b{{font-size:12px;font-family:ui-monospace,monospace}}
.sw .t{{padding:8px 2px}}.sw .t b{{display:block}}.sw .t span{{display:block;color:{TX};font-size:12px}}.sw .t i{{display:block;color:{MUT};font-size:10.5px;font-style:normal;margin-top:2px}}
.chips{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;background:{PANEL};border:1px solid #1b232e;border-radius:12px;padding:16px}}.ch{{padding:4px 10px;border-radius:6px;font-weight:700;font-size:12px;background:rgba(var(--c),.14)}}.btn{{margin-left:auto;color:#FF1179;border:1px solid rgba(255,17,121,.45);border-radius:8px;padding:7px 14px;font-weight:600}}
table{{border-collapse:collapse;width:100%;font-size:12.5px}}th,td{{text-align:left;padding:6px 10px;border-bottom:1px solid #1b232e}}th{{color:{MUT};font-weight:500}}.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px}}
.cws{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.cw{{background:{PANEL};border:1px solid #1b232e;border-radius:16px;padding:20px;text-align:center}}.big{{width:190px;height:190px;margin:0 auto 10px;background:{BG};border-radius:40px;padding:22px;border:1px solid #1f2735}}.big svg{{width:100%;height:100%}}
.cw h4{{margin:6px 0 2px;font-size:15px}}.cw p{{margin:0 0 14px;color:{MUT};font-size:12px}}.row{{display:flex;gap:18px;justify-content:center;align-items:flex-end}}.row div{{display:flex;flex-direction:column;align-items:center;gap:6px}}small{{color:{MUT};font-size:10.5px}}
.i180{{width:72px;height:72px;border-radius:16px}}.i32{{width:32px;height:32px}}.i16{{width:16px;height:16px;display:block}}.i16 svg,.lm svg{{width:100%;height:100%;display:block}}.row .lk{{flex-direction:row;gap:8px;background:{BG};padding:8px 12px;border-radius:10px;margin-left:6px}}.lm{{width:28px;height:28px}}.lk b{{letter-spacing:.1em;font-size:16px}}
.note{{color:{MUT};font-size:12px;margin-top:10px}}'''
doc = f'''<!doctype html><meta charset="utf-8"><style>{css}</style><h1>No Risk No Money · paleta NRNM</h1><p class="sub">Fondo casi negro #0b0e13 + 3 acentos tomados de tus fotos (mediana de píxeles). Roles: rosa = marca/CTA, teal = positivo, azul = en vivo/info.</p>
<div class="sws">{sw}</div><h3>Roles en la interfaz</h3><div class="chips">{chips}</div>
<h3>Contraste WCAG (texto sobre fondo / tarjeta; texto oscuro sobre el color)</h3><table><tr><th>Color</th><th>Hex</th><th>sobre #0b0e13</th><th>sobre #11161d</th><th>Texto (AA 4.5)</th><th>#0b0e13 sobre el color (botón relleno)</th></tr>{rows}</table>
<p class="note">Botón relleno rosa: texto oscuro (5.16:1). Texto blanco sobre rosa solo da 3.74:1, no pasa AA para texto normal.</p>
<h3>Colorways del logo (variante A · triángulo + ojo + pelota + línea de cancha)</h3><div class="cws">{cws}</div>'''
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"]); pg = br.new_page(viewport={"width": 1350, "height": 900}, device_scale_factor=2)
    pg.set_content(doc); pg.wait_for_timeout(300); pg.screenshot(path=os.path.join(ROOT, "screens/nrnm_paleta.png"), full_page=True); br.close()
print("ok")
