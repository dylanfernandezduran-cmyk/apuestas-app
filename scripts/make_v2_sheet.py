#!/usr/bin/env python3
"""Hoja screens/nrnm_v2_options.png: cada opción grande sobre ícono redondeado carbón (como la referencia), 32 px, 16 px y etiqueta."""
import os, json, base64, html
from playwright.sync_api import sync_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); B = os.path.join(ROOT, "static/brand")
cfg = json.load(open(f"{B}/brand.json", encoding="utf-8")); ids = [f"nrnm_v2_{i}" for i in range(1, 6)]
def b64(k, f): return "data:image/png;base64," + base64.b64encode(open(f"{B}/{k}/icons/{f}", "rb").read()).decode()
cards = ""
for k in ids:
    o = cfg["options"][k]; g = open(f"{B}/{k}/glyph.svg").read()
    cards += f'<section><div class="ic">{g}</div><h4>{html.escape(o["label"])}</h4><p>{html.escape(o["desc"])}</p><div class="sm"><div><img class="a32" src="{b64(k, "favicon-32.png")}"><small>32 px</small></div><div><span class="a16" style="background:#171b21">{g}</span><small>16 px</small></div><div><img class="a60" src="{b64(k, "apple-touch-icon.png")}"><small>iPhone</small></div></div><div class="lk"><span class="lm">{g}</span><span><b>NRNM</b><i>No Risk No Money</i></span></div></section>'
css = '''*{box-sizing:border-box}body{margin:0;width:1500px;padding:34px 36px;background:#0b0e13;color:#e6ebf2;font:14px/1.45 -apple-system,Inter,system-ui,sans-serif}h1{font-size:24px;margin:0 0 4px}.sub{color:#7f8b9c;margin:0 0 22px}
.g{display:grid;grid-template-columns:repeat(5,1fr);gap:16px}section{background:#11161d;border:1px solid #1b232e;border-radius:18px;padding:20px 16px;text-align:center}
.ic{width:210px;height:210px;margin:0 auto 14px;border-radius:48px;padding:26px;background:linear-gradient(160deg,#242932 0%,#171b21 55%,#101318 100%);border:1px solid #2c323c;box-shadow:0 14px 30px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.06)}.ic svg{width:100%;height:100%;display:block}
h4{margin:4px 0 2px;font-size:14.5px}p{margin:0 0 14px;color:#7f8b9c;font-size:11.5px;min-height:34px}.sm{display:flex;gap:18px;justify-content:center;align-items:flex-end;margin-bottom:12px}.sm div{display:flex;flex-direction:column;align-items:center;gap:6px}
small{color:#7f8b9c;font-size:10.5px}.a32{width:32px;height:32px}.a16{display:block;width:16px;height:16px}.a16 svg{width:100%;height:100%;display:block}.a60{width:60px;height:60px;border-radius:13.4px}
.lk{display:flex;align-items:center;gap:10px;justify-content:center;background:#0b0e13;border-radius:12px;padding:10px}.lm{width:32px;height:32px}.lm svg{width:100%;height:100%;display:block}.lk b{display:block;font-size:16px;letter-spacing:.1em}.lk i{display:block;font-style:normal;font-size:9.5px;color:#7f8b9c;letter-spacing:.06em;text-align:left}'''
doc = f'<!doctype html><meta charset="utf-8"><style>{css}</style><h1>NRNM v2 · triángulo + ojo (sin porterías ni balones)</h1><p class="sub">Estilo de tu referencia: triángulo monolínea con vértice cruzado, ojo almendrado con iris, pupila y brillo, barra corta. Paleta: rosa #FF1179 · azul #3C85F7 · teal #06AAC4 · carbón #171b21 / fondo #0b0e13.</p><div class="g">{cards}</div>'
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"]); pg = br.new_page(viewport={"width": 1500, "height": 700}, device_scale_factor=2)
    pg.set_content(doc); pg.wait_for_timeout(300); pg.screenshot(path=os.path.join(ROOT, "screens/nrnm_v2_options.png"), full_page=True); br.close()
