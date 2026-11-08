"""Una sola vez: califica con el resultado real los picks ANULADO que sí tienen resultado.
- cancelados/invertidos antes del inicio (sin otro pick vivo/más reciente del mismo juego+mercado) -> vía grading.grade_pending
- tenis con retiro a media partida -> ML con el ganador real (los demás mercados siguen anulados)
Uso: APUESTAS_DB=data/history.db python -m scripts.regrade_voided [--dry]"""
import asyncio, sys, json, time
from server import record as R, grading as G

async def main(dry):
    now = time.time()
    before = {r["id"]: r for r in R._rows("SELECT * FROM picks WHERE status='ANULADO'")}
    cand = [r for r in R.pending(now, 5000) if r["status"] == "ANULADO"]
    ret = [r for r in before.values() if r["sport"] == "tenis" and (r["note"] or "").startswith("Partido sin final normal (Retired")]
    out = []
    for r in cand + ret:
        res = await G.fetch_result(r)
        g = G.grade_row(r, res, now)
        out.append(dict(id=r["id"], lg=r["league"], eid=r["eid"], game=f"{r['home']} vs {r['away']}", mk=r["market"], sel=r["selection"], line=r["line"], odds=r["odds"],
                        why=r["state"] or "RETIRO", res=res.get("state"), new=g[0] if g else None, units=g[1] if g else None, score=g[2] if g else None))
        if g and not dry and g[0] != "ANULADO":
            note = f"{'Retiro' if r in ret else ('Invertido' if r['state']=='INVERTIDO' else 'Cancelado')} antes/durante; calificado con el resultado real a la línea registrada" + (f"; {g[5]}" if g[5] else "")
            R.set_grade(r["id"], g[0], g[1], g[2], g[3], g[4], note, now=now)
        elif g and not dry and g[0] == "ANULADO" and r in cand:
            R.set_grade(r["id"], "ANULADO", None, g[2], None, None, r["note"], now=now)   # marca graded_at: no se reintenta
    print(json.dumps(out, ensure_ascii=False, indent=0))
    # los que quedan fuera (duplicado/otro lado vivo)
    ids = {o["id"] for o in out}
    print("SKIPPED", json.dumps([dict(id=r["id"], lg=r["league"], eid=r["eid"], mk=r["market"], sel=r["selection"], state=r["state"], start=r["start_ts"] <= now)
                                  for r in before.values() if r["id"] not in ids and r["state"] in ("CANCELADO", "INVERTIDO")]))

if __name__ == "__main__":
    asyncio.run(main("--dry" in sys.argv))
