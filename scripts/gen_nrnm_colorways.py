#!/usr/bin/env python3
"""Colorways del logo NRNM (variante A: triángulo + ojo + pupila-pelota + línea de cancha).
Genera static/brand/{nrnm,nrnm_degradado,nrnm_azul}/glyph.svg"""
import os
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PINK, TEAL, BLUE, BG, WHITE = "#FF1179", "#06AAC4", "#3C85F7", "#0b0e13", "#e6ebf2"
H = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" fill="none" stroke-linecap="round" stroke-linejoin="round">'
def logo(tri, eye, ball, base=None, defs="", gid=None):
    base = base or tri
    return (H + defs + f'<path d="M256 52 L460 432 L52 432 Z" stroke="{tri}" stroke-width="30"/><path d="M26 432 H486" stroke="{base}" stroke-width="30"/>'
            f'<path d="M146 342 Q256 238 366 342 Q256 446 146 342 Z" stroke="{eye}" stroke-width="28"/>'
            f'<circle cx="256" cy="342" r="48" fill="{ball}"/><g stroke="{BG}" stroke-width="11"><path d="M229 308 Q253 342 229 376"/><path d="M283 308 Q259 342 283 376"/></g></svg>')
grad = f'<defs><linearGradient id="nrnmg" gradientUnits="userSpaceOnUse" x1="40" y1="60" x2="480" y2="440"><stop offset="0" stop-color="{PINK}"/><stop offset="1" stop-color="{BLUE}"/></linearGradient></defs>'
CW = {
  "nrnm":            logo(PINK, WHITE, TEAL),                                    # Rosa neón: triángulo rosa, ojo blanco, pelota teal
  "nrnm_degradado":  logo("url(#nrnmg)", WHITE, PINK, base=BLUE, defs=grad),     # triángulo con degradado rosa→azul sutil, pelota rosa
  "nrnm_azul":       logo(BLUE, WHITE, TEAL, base=TEAL),                         # frío: triángulo azul, base y pelota teal
}
if __name__ == "__main__":
    for k, v in CW.items():
        os.makedirs(os.path.join(ROOT, "static/brand", k), exist_ok=True)
        open(os.path.join(ROOT, "static/brand", k, "glyph.svg"), "w").write(v)
