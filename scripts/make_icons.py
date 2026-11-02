#!/usr/bin/env python3
"""Genera los iconos PWA (192/512/maskable/apple-touch-icon 180/favicon) de la marca activa (static/brand/brand.json) con Chrome headless.
Uso:  python3 scripts/make_icons.py [opcion] [--preview]     (si das la opción, también la deja como activa: ventaja | pizarra | vigia)
Requiere: playwright (python) + google-chrome. Cambiar de marca = editar brand.json (active) o pasar la opción aquí; no hay que tocar código."""
import json, os, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
B = os.path.join(ROOT, "static", "brand")
cfg = json.load(open(os.path.join(B, "brand.json"), encoding="utf-8"))
args = [a for a in sys.argv[1:] if not a.startswith("--")]
PREVIEW = "--preview" in sys.argv     # --preview: genera los íconos de la opción en static/brand/<opcion>/icons SIN cambiar la marca activa
if args:
    assert args[0] in cfg["options"], f"opciones: {list(cfg['options'])}"
    if not PREVIEW:
        cfg["active"] = args[0]
        json.dump(cfg, open(os.path.join(B, "brand.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
act = args[0] if args else cfg["active"]; bg = cfg["theme"]["bg"]
glyph = open(os.path.join(B, act, "glyph.svg"), encoding="utf-8").read()
inner = glyph[glyph.index(">") + 1: glyph.rindex("</svg>")]
head = glyph[:glyph.index(">") + 1]

def icon_svg(full_bleed, scale=1.0):
    r = 0 if full_bleed else 112
    s = scale
    t = f'translate({256*(1-s)} {256*(1-s)}) scale({s})'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="{r}" fill="{bg}"/>'
            f'<g transform="{t}">{head.replace("<svg", "<g").replace(" xmlns=\"http://www.w3.org/2000/svg\"", "").replace(" viewBox=\"0 0 512 512\"", "")}{inner}</g></g></svg>')

from playwright.sync_api import sync_playwright
out = os.path.join(B, act, "icons") if PREVIEW else os.path.join(B, "icons"); os.makedirs(out, exist_ok=True)
jobs = [("icon-192.png", 192, False, 1.0), ("icon-512.png", 512, False, 1.0), ("maskable-512.png", 512, True, 0.78), ("apple-touch-icon.png", 180, True, 0.92), ("favicon-32.png", 32, False, 1.0)]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for name, size, fb, sc in jobs:
        pg = b.new_page(viewport={"width": size, "height": size})
        pg.set_content(f'<html><body style="margin:0;background:transparent">{icon_svg(fb, sc).replace("<svg ", f"<svg width={size} height={size} ", 1)}</body></html>')
        pg.screenshot(path=os.path.join(out, name), omit_background=True)
        pg.close()
    b.close()
print("iconos generados para", act, "->", out)
