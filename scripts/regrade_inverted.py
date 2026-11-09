"""Califica ANULADO INVERTIDO/CANCELADO con resultado real; dedupe de mercados."""
import asyncio, time, json, sys
from server import record as R, grading as G

async def main(dry=False):
    now = time.time()
    n = R.activate_started(now)
    print('activated', n)
    rows = [r for r in R.pending(now, 5000) if r['status']=='PENDIENTE' or r.get('state') in ('CANCELADO','INVERTIDO','ACTIVO')]
    # focus tennis finals of interest + all pending
    out = await G.grade_pending(now, limit=2000)
    print('grade_pending', out)
    # explicit pass for known eids
    for eid in ['186529','186537','186536','186535']:
        rows = R._rows("select id,label,status,state,note,score_text from picks where eid=? order by id",(eid,))
        print('==', eid)
        for r in rows: print(' ', r['id'], r['label'], r['status'], r['state'], r.get('score_text'), (r.get('note') or '')[:50])

if __name__ == '__main__':
    asyncio.run(main('--dry' in sys.argv))
