import math
W="#e6ebf2"; G="#34d399"; BG="#0b0e13"
H='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" fill="none" stroke-linecap="round" stroke-linejoin="round">'
def gen(A=G):
    v={}
    # 1: triángulo + ojo con pupila-pelota + línea de cancha como base
    v['tri_bola']=H+(f'<path d="M256 52 L460 432 L52 432 Z" stroke="{W}" stroke-width="30"/><path d="M26 432 H486" stroke="{W}" stroke-width="30"/>'
      f'<path d="M146 342 Q256 238 366 342 Q256 446 146 342 Z" stroke="{W}" stroke-width="28"/>'
      f'<circle cx="256" cy="342" r="48" fill="{A}"/><g stroke="{BG}" stroke-width="11"><path d="M229 308 Q253 342 229 376"/><path d="M283 308 Q259 342 283 376"/></g></svg>')
    # 2: rayos finos + signos +/− (momios) 
    rays=''
    for a in (-52,-32,-12,12,32,52):
        r1,r2=232,282; cx,cy=256,296
        x1=cx+r1*math.sin(math.radians(a)); y1=cy-r1*math.cos(math.radians(a)); x2=cx+r2*math.sin(math.radians(a)); y2=cy-r2*math.cos(math.radians(a))
        rays+=f'<path d="M{x1:.0f} {y1:.0f} L{x2:.0f} {y2:.0f}"/>'
    v['tri_rayos']=H+(f'<g stroke="{A}" stroke-width="14" opacity=".9">{rays}</g>'
      f'<path d="M256 74 L430 420 L82 420 Z" stroke="{W}" stroke-width="28"/>'
      f'<path d="M158 318 Q256 226 354 318 Q256 410 158 318 Z" stroke="{W}" stroke-width="24"/><circle cx="256" cy="318" r="32" fill="{A}"/>'
      f'<g stroke="{A}" stroke-width="16"><path d="M36 372 H76 M56 352 V392"/><path d="M436 372 H476"/></g></svg>')
    # 3: el ojo Avizor es la base de la pirámide (sus esquinas son las esquinas del triángulo)
    v['tri_avizor']=H+(f'<path d="M78 366 L256 58 L434 366" stroke="{W}" stroke-width="30"/>'
      f'<path d="M78 366 Q256 226 434 366 Q256 506 78 366 Z" stroke="{W}" stroke-width="30" fill="{BG}"/>'
      f'<circle cx="256" cy="366" r="56" fill="{A}"/><g stroke="{BG}" stroke-width="13"><path d="M222 326 Q254 366 222 406"/><path d="M290 326 Q258 366 290 406"/></g></svg>')
    # 4: insignia monolínea: aro + triángulo + ojo mínimo; la base (línea de cancha) y la pupila en verde
    v['tri_badge']=H+(f'<circle cx="256" cy="256" r="222" stroke="{W}" stroke-width="22"/>'
      f'<path d="M104 360 L256 78 L408 360" stroke="{W}" stroke-width="22"/><path d="M104 360 H408" stroke="{A}" stroke-width="22"/>'
      f'<path d="M172 288 Q256 218 340 288 Q256 358 172 288 Z" stroke="{W}" stroke-width="20"/><circle cx="256" cy="288" r="24" fill="{A}"/></svg>')
    return v
if __name__=='__main__':
    for k,s in gen().items(): open(f'static/brand/{k}/glyph.svg','w').write(s)
