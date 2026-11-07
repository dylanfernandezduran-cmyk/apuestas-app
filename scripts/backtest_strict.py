"""Backtest de los umbrales del pick oficial sobre el récord REAL calificado (SQLite). uso: python scripts/backtest_strict.py [ruta.db]"""
import sys
import sqlite3,json,itertools
from collections import defaultdict
c=sqlite3.connect(sys.argv[1] if len(sys.argv)>1 else 'data/history.db'); c.row_factory=sqlite3.Row
P={(r['league'],r['eid']):json.loads(r['payload']) for r in c.execute("select * from predictions")}
R=[dict(r) for r in c.execute("select * from picks where status in ('GANADO','PERDIDO','PUSH','MEDIO_GANADO','MEDIO_PERDIDO')")]
def imp(o): return -o/(-o+100) if o<0 else 100/(o+100)
def agree(r):
    p=P.get((r['league'],r['eid']))
    if not p: return None
    m=r['market']
    if m=='ml': return (p.get('winner') or {}).get('side')==r['selection']
    if m in('total','spread','btts'):
        s=(p.get(m) or {}).get('side'); return None if s is None else s==r['selection']
    if m=='sspread': return (p.get('winner') or {}).get('side')==r['selection'] if 'winner' in p else None
    return None
def mv(r):
    """+1 si la línea/cuota se movió a favor del pick (dinero del mercado del mismo lado), -1 en contra, 0 sin cambio"""
    m,s=r['market'],r['selection']
    if r['open_line'] is not None and r['line'] is not None and r['open_line']!=r['line']:
        d=r['line']-r['open_line']
        if m in('total','stotal'): return 1 if (d>0)==(s=='over') else -1
        if m in('spread','sspread'): return 1 if d<0 else -1   # línea del lado elegido baja = más cara = dinero de ese lado
    if r['open_odds'] is not None and r['odds'] is not None and r['open_odds']!=r['odds']:
        return 1 if imp(r['odds'])>imp(r['open_odds']) else -1
    return 0
for r in R: r['agree']=agree(r); r['mv']=mv(r)
def st(rows):
    W=sum(r['status']=='GANADO' for r in rows)+.5*sum(r['status']=='MEDIO_GANADO' for r in rows);L=sum(r['status']=='PERDIDO' for r in rows)+.5*sum(r['status']=='MEDIO_PERDIDO' for r in rows)
    u=sum(r['units'] or 0 for r in rows); n=sum(r['units'] is not None for r in rows)
    return dict(n=len(rows),W=W,L=L,hit=W/(W+L)*100 if W+L else 0,u=round(u,2),roi=u/n*100 if n else 0)
def fmt(name,s): return f"{name:52s} n={s['n']:4d} {s['W']:.0f}-{s['L']:.0f} hit={s['hit']:5.1f}% u={s['u']:+7.2f} roi={s['roi']:+6.1f}%"
print(fmt('ALL',st(R)))
for a in (True,False,None): print(fmt(f'agree={a}',st([r for r in R if r['agree'] is a])))
for m in (1,0,-1): print(fmt(f'mv={m}',st([r for r in R if r['mv']==m])))
def score(r): return (r['edge'] or 0)/100*2 + (r['p_final'] or 0)
def policy(rows,e,p,need_agree,no_against,basis,maxml):
    ok=[r for r in rows if (r['edge'] or -99)>=e and (r['p_final'] or 0)>=p and (not need_agree or r['agree'] is not False) and (not no_against or r['mv']>=0) and (basis is None or r['basis']==basis) and (maxml is None or r['market']!='ml' or (r['odds'] or 0)>=maxml)]
    best={}
    for r in ok:
        k=(r['league'],r['eid'])
        if k not in best or score(r)>score(best[k]): best[k]=r
    return list(best.values())
res=[]
for e,p,ag,na,b,mx in itertools.product((0,1,2,3,4),(0.5,0.52,0.55,0.58),(True,),(True,False),(None,'modelo'),(None,-250)):
    s=st(policy(R,e,p,ag,na,b,mx)); res.append(((e,p,ag,na,b,mx),s))
res=[x for x in res if x[1]['n']>=40]
res.sort(key=lambda x:-x[1]['roi'])
for k,s in res[:12]: print(fmt(str(k),s))
print('ganadores frágiles: muestra pequeña')
print('--- vecindad (1 por juego, coherente con predicción)')
for e in (1,2,3):
  for p in (0.52,0.55,0.58):
    print(fmt(f'edge>={e} p>={p}',st(policy(R,e,p,True,False,None,None))))
CH=(2,0.55)
sel=policy(R,CH[0],CH[1],True,False,None,None)
print('--- elegido', CH)
for sp in ('nba','nhl','nfl','futbol','tenis'): print(fmt(' '+sp,st([r for r in sel if r['sport']==sp])))
import time
for d0,d1 in (('2026-11-02','2026-11-04'),('2026-11-05','2026-11-07')):
    f=lambda r: d0<=time.strftime('%Y-%m-%d',time.gmtime(r['start_ts']-21600))<=d1
    print(fmt(f' {d0}..{d1} antes',st([r for r in R if f(r)])), '\n', fmt(f' {d0}..{d1} después',st([r for r in sel if f(r)])))
print('--- fútbol detalle (1/juego, edge>=2,p>=.55)')
F=[r for r in R if r['sport']=='futbol']
for e in (2,4,6,8): print(fmt(f' futbol edge>={e}',st(policy(F,e,0.55,True,False,None,None))))
for e in (2,4,6): print(fmt(f' futbol edge>={e} p>=.6',st(policy(F,e,0.60,True,False,None,None))))
print(fmt(' futbol todos',st(F)))
for sp in ('nba','nhl','tenis'):
  for e,p in ((2,.55),(3,.58)): print(fmt(f' {sp} e{e} p{p}',st(policy([r for r in R if r['sport']==sp],e,p,True,False,None,None))))
