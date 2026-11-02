#!/usr/bin/env python3
"""NRNM v2: logo estilo referencia (triángulo monolínea con vértice que se cruza + ojo almendrado con iris/pupila/brillo + barra corta), SIN porterías ni balones.
Genera static/brand/nrnm_v2_{1..5}/glyph.svg y las registra en brand.json (sin tocar 'active')."""
import os, json
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PINK, BLUE, TEAL, BG, WHITE = "#FF1179", "#3C85F7", "#06AAC4", "#0b0e13", "#FFFFFF"
H = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" fill="none" stroke-linecap="round" stroke-linejoin="round">'
def logo(tri, eye=None, bar=None, iris=PINK, defs="", pupil="#14181e"):
    eye = eye or tri; bar = bar or tri
    return (H + defs + '<g transform="translate(0 14)">'
        f'<path d="M72 430 L263 70" stroke="{tri}" stroke-width="26"/><path d="M440 430 L249 70" stroke="{tri}" stroke-width="26"/>'          # patas; el vértice se cruza y sobresale
        f'<path d="M162 298 Q256 194 350 298 Q256 402 162 298 Z" stroke="{eye}" stroke-width="22"/>'                                    # ojo almendrado
        f'<circle cx="256" cy="298" r="35" fill="{iris}"/><circle cx="256" cy="298" r="16" fill="{pupil}"/><circle cx="263" cy="291" r="6" fill="{WHITE}"/>'  # iris + pupila + brillo
        f'<path d="M208 404 H304" stroke="{bar}" stroke-width="22"/></g></svg>')
def grad(i, stops, x1=0, y1=0, x2=0, y2=1):  # coordenadas absolutas del lienzo 512 (userSpaceOnUse)
    st = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    return f'<defs><linearGradient id="v2g{i}" gradientUnits="userSpaceOnUse" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{st}</linearGradient></defs>', f"url(#v2g{i})"
d4, g4 = grad(4, [(0, "#FF8DBE"), (.4, PINK), (1, "#D10A62")], 180, 60, 330, 430)
d5, g5 = grad(5, [(0, PINK), (1, BLUE)], 90, 70, 430, 430)
OPT = {
 1: ("1 · Todo rosa", "Triángulo, ojo y barra rosa; iris rosa con pupila oscura y brillo.", logo(PINK)),
 2: ("2 · Rosa + iris teal", "Triángulo rosa, iris teal #06AAC4.", logo(PINK, iris=TEAL)),
 3: ("3 · Rosa + iris azul", "Triángulo rosa, iris azul Porsche #3C85F7.", logo(PINK, iris=BLUE)),
 4: ("4 · Rosa metálico + teal", "Brillo metálico: degradado rosa claro → rosa → rosa profundo; iris teal.", logo(g4, iris=TEAL, defs=d4)),
 5: ("5 · Degradado rosa→azul + teal", "Triángulo, ojo y barra con degradado rosa→azul; iris teal.", logo(g5, iris=TEAL, defs=d5)),
}
if __name__ == "__main__":
    bj = os.path.join(ROOT, "static/brand/brand.json"); b = json.load(open(bj, encoding="utf-8")); pal = b["options"]["nrnm"]["palette"]
    for n, (lab, desc, svg) in OPT.items():
        k = f"nrnm_v2_{n}"; os.makedirs(os.path.join(ROOT, "static/brand", k), exist_ok=True)
        open(os.path.join(ROOT, "static/brand", k, "glyph.svg"), "w").write(svg)
        b["options"][k] = dict(name="No Risk No Money", short="NRNM", tagline="Riesgo medido, picks con datos", palette=pal, label=lab, desc=desc, icon_bg="#171b21")
    json.dump(b, open(bj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
