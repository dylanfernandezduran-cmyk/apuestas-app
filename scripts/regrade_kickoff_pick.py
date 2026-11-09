"""Aplica la regla: cuenta el pick en vigor al inicio (el más reciente no anulado).
- Deshace SUPERSEDED (vuelven a PENDIENTE para recalificar).
- Los originales que quedaron calificados por error se anulan vía dedupe_market (conserva el más reciente).
- CANCELADO sin reemplazo se reactivan y califican.
"""
import asyncio, time
from server import record as R, grading as G

async def main():
    now = time.time()
    with R.history._lock:
        c = R._c()
        n_sup = c.execute(
            "UPDATE picks SET status='PENDIENTE', state='ACTIVO', units=NULL, graded_at=NULL, "
            "score_text=NULL, final_home=NULL, final_away=NULL, updated_at=?, note=? "
            "WHERE status='ANULADO' AND state='SUPERSEDED'",
            (int(now), "Restaurado: se cuenta el pick actualizado en vigor al saque (no el invertido)")
        ).rowcount
        # Cualquier pick calificado que sea el lado VIEJO de un invertido: si hay un hermano más nuevo
        # del mismo mercado (cualquier status), el dedupe lo limpiará tras reactivar supersededs.
        # También: picks que reactivamos como INVERTIDO y calificamos (quedaron ACTIVO/GANADO) con id menor
        # que otro del mismo mercado — dedupe_market los anula.
        c.commit()
    print('restored_superseded', n_sup)
    # Reactivar solo CANCELADO sin reemplazo
    print('activate_cancelado', R.activate_started(now))
    # Dedupe todos los mercados con >1 pick vivo
    pairs = R._rows(
        "SELECT league, eid, market, COUNT(*) n FROM picks "
        "WHERE status IN ('GANADO','PERDIDO','PUSH','MEDIO_GANADO','MEDIO_PERDIDO','PENDIENTE') "
        "GROUP BY league, eid, market HAVING n>1")
    nd = 0
    for p in pairs:
        nd += R.dedupe_market(p['league'], p['eid'], p['market'], now=now)
    print('deduped', nd, 'markets', len(pairs))
    out = await G.grade_pending(now, limit=5000)
    print('grade_pending', out)
    for eid in ['186529','186537','186536','186535']:
        print('==', eid)
        for r in R._rows("select id,label,status,state,score_text from picks where eid=? order by id",(eid,)):
            print(' ', r['id'], r['label'], r['status'], r['state'], r.get('score_text'))
    s = R.summary()
    print('summary', {k: s.get(k) for k in ('W','L','P','units','win_pct','void','pending','total','graded')})

if __name__ == '__main__':
    asyncio.run(main())
