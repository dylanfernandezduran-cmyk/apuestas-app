#!/usr/bin/env python3
"""NRNM final: triángulo completo (cerrado) + ojo almendrado, todo rosa #FF1179, sin barra. 'nrnm_final' = pupila normal; variantes con la iris/pupila como balón.
Genera static/brand/nrnm_final{,_futbol,_basket,_beisbol,_americano}/glyph.svg y las registra en brand.json (no cambia 'active')."""
import os, json, math
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PINK, DK, WH = "#FF1179", "#14181e", "#FFFFFF"
H = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" fill="none" stroke-linecap="round" stroke-linejoin="round">'
CX, CY = 256, 322
def frame(inner, col=PINK):
    return (H + '<g transform="translate(0 8)">'
            f'<path d="M256 66 L446 432 H66 Z" stroke="{col}" stroke-width="28"/>'
            f'<path d="M162 {CY} Q256 218 350 {CY} Q256 426 162 {CY} Z" stroke="{col}" stroke-width="22"/>' + inner + '</g></svg>')
def pent(r, rot=-90):
    return " ".join(f"{CX + r * math.cos(math.radians(rot + 72 * i)):.1f},{CY + r * math.sin(math.radians(rot + 72 * i)):.1f}" for i in range(5))
plain = f'<circle cx="{CX}" cy="{CY}" r="36" fill="{PINK}"/><circle cx="{CX}" cy="{CY}" r="16" fill="{DK}"/><circle cx="{CX + 7}" cy="{CY - 7}" r="6" fill="{WH}"/>'
def ball_base(r=38): return f'<circle cx="{CX}" cy="{CY}" r="{r}" fill="{PINK}"/>'
# fútbol: pentágono central oscuro con 5 líneas hacia el borde
spokes = "".join(f'<path d="M{CX + 14 * math.cos(math.radians(-90 + 72 * i)):.1f} {CY + 14 * math.sin(math.radians(-90 + 72 * i)):.1f} L{CX + 34 * math.cos(math.radians(-90 + 72 * i)):.1f} {CY + 34 * math.sin(math.radians(-90 + 72 * i)):.1f}"/>' for i in range(5))
futbol = ball_base() + f'<polygon points="{pent(15)}" fill="{DK}" stroke="{DK}" stroke-width="4" stroke-linejoin="round"/><g stroke="{DK}" stroke-width="5">{spokes}</g>'
# basquetbol: cruz + dos arcos laterales
basket = ball_base() + f'<g stroke="{DK}" stroke-width="5"><path d="M{CX} {CY - 38} V{CY + 38}"/><path d="M{CX - 38} {CY} H{CX + 38}"/><path d="M{CX - 27} {CY - 27} Q{CX - 10} {CY} {CX - 27} {CY + 27}"/><path d="M{CX + 27} {CY - 27} Q{CX + 10} {CY} {CX + 27} {CY + 27}"/></g>'
# béisbol: dos costuras curvas con puntadas
beis = ball_base() + f'<g stroke="{DK}" stroke-width="4.5"><path d="M{CX - 24} {CY - 28} Q{CX - 8} {CY} {CX - 24} {CY + 28}"/><path d="M{CX + 24} {CY - 28} Q{CX + 8} {CY} {CX + 24} {CY + 28}"/>' + "".join(f'<path d="M{CX - 18} {CY + y} h-8"/><path d="M{CX + 18} {CY + y} h8"/>' for y in (-14, 0, 14)) + '</g>'
# americano: balón ovalado inclinado con cordones y franjas (fill/line configurables)
def americano(fill=PINK, line=DK, stroke=None):
    el = f'<ellipse cx="{CX}" cy="{CY}" rx="46" ry="28" fill="{fill}"' + (f' stroke="{stroke}" stroke-width="6"/>' if stroke else '/>')
    return (f'<g transform="rotate(-28 {CX} {CY})">{el}<g stroke="{line}" stroke-width="5">'
            f'<path d="M{CX - 16} {CY} H{CX + 16}"/><path d="M{CX - 9} {CY - 9} V{CY + 9}"/><path d="M{CX} {CY - 9} V{CY + 9}"/><path d="M{CX + 9} {CY - 9} V{CY + 9}"/>'
            f'<path d="M{CX - 33} {CY - 15} Q{CX - 38} {CY} {CX - 33} {CY + 15}"/><path d="M{CX + 33} {CY - 15} Q{CX + 38} {CY} {CX + 33} {CY + 15}"/></g></g>')
amer = americano()
amer_w = americano(fill="#FFFFFF", line=DK)                       # balón blanco, cordones oscuros
amer_wo = americano(fill=DK, line="#FFFFFF", stroke="#FFFFFF")   # solo contorno blanco, interior oscuro
K, W = "#000000", "#FFFFFF"
plain_w = f'<circle cx="{CX}" cy="{CY}" r="36" fill="{W}"/><circle cx="{CX}" cy="{CY}" r="16" fill="{K}"/><circle cx="{CX + 7}" cy="{CY - 7}" r="6" fill="{W}"/>'
WHITE_OPT = {"nrnm_final_blanco": ("Blanco · pupila", "Todo blanco sobre negro puro #000: triángulo completo, ojo y pupila.", plain_w),
             "nrnm_final_blanco_americano": ("Blanco · balón americano", "Todo blanco sobre negro puro #000; el iris es un balón americano con cordones en negativo (negros).", americano(fill=W, line=K))}
OPT = {"nrnm_final": ("Final · pupila", "Triángulo completo + ojo, todo rosa; pupila oscura con brillo.", plain),
       "nrnm_final_futbol": ("Fútbol", "Iris/pupila = balón de fútbol (pentágono central).", futbol),
       "nrnm_final_basket": ("Básquetbol", "Iris/pupila = balón de básquetbol (cruz y arcos).", basket),
       "nrnm_final_beisbol": ("Béisbol", "Iris/pupila = pelota de béisbol (costuras con puntadas).", beis),
       "nrnm_final_americano": ("Fútbol americano", "Iris/pupila = balón ovalado con cordones.", amer),
       "nrnm_final_americano_blanco": ("Americano blanco", "Triángulo y ojo rosas; el balón ovalado es blanco con cordones oscuros.", amer_w),
       "nrnm_final_americano_contorno": ("Americano contorno blanco", "Triángulo y ojo rosas; balón solo con contorno y cordones blancos, interior oscuro.", amer_wo)}
if __name__ == "__main__":
    bj = os.path.join(ROOT, "static/brand/brand.json"); b = json.load(open(bj, encoding="utf-8")); pal = b["options"]["nrnm"]["palette"]
    for k, (lab, desc, inner) in OPT.items():
        os.makedirs(os.path.join(ROOT, "static/brand", k), exist_ok=True); open(os.path.join(ROOT, "static/brand", k, "glyph.svg"), "w").write(frame(inner))
        b["options"][k] = dict(name="No Risk No Money", short="NRNM", tagline="Riesgo medido, picks con datos", palette=pal, label=lab, desc=desc, icon_bg="#171b21")
    for k, (lab, desc, inner) in WHITE_OPT.items():
        os.makedirs(os.path.join(ROOT, "static/brand", k), exist_ok=True); open(os.path.join(ROOT, "static/brand", k, "glyph.svg"), "w").write(frame(inner, W))
        b["options"][k] = dict(name="No Risk No Money", short="NRNM", tagline="Riesgo medido, picks con datos", palette=pal, label=lab, desc=desc, icon_bg=K)
    json.dump(b, open(bj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
