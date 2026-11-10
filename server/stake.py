"""Stake de paper trading: 1/4 Kelly, tope 2% por pick y 8% de exposición diaria.
1u = unit_pct % de la bankroll (por defecto 1%). No apuesta dinero real."""
from .odds import am_to_dec

KELLY_FRAC = 0.25
CAP_PICK = 0.02
CAP_DAILY = 0.08
DEFAULT_UNIT_PCT = 1.0  # 1u = 1% de la bankroll

def quarter_kelly(p, price, bankroll, unit_pct=DEFAULT_UNIT_PCT, daily_used_frac=0.0,
                  cap_pick=CAP_PICK, cap_daily=CAP_DAILY):
    """p: prob. final (0-1); price: momio americano o decimal > 1.
    Devuelve dict o None si faltan datos. frac<=0 si no hay edge positivo."""
    if p is None or price is None or bankroll is None:
        return None
    try:
        p = float(p); bankroll = float(bankroll)
        unit_pct = float(unit_pct if unit_pct is not None else DEFAULT_UNIT_PCT)
        daily_used_frac = float(daily_used_frac or 0)
    except (TypeError, ValueError):
        return None
    if bankroll <= 0 or not (0 < p < 1):
        return None
    try:
        x = float(price)
    except (TypeError, ValueError):
        return None
    # americano típico: <= -100 o >= +100; decimal: 1 < x < 100
    if x <= -100 or x >= 100:
        dec = am_to_dec(int(x))
    elif x > 1:
        dec = x
    else:
        return None
    if not dec or dec <= 1:
        return None
    b = dec - 1.0
    q = 1.0 - p
    f_full = (b * p - q) / b
    f_q = f_full * KELLY_FRAC
    remaining = max(0.0, cap_daily - daily_used_frac)
    reasons = []
    f = f_q
    if f <= 0:
        return dict(frac=0.0, stake=0.0, units=0.0, capped=False, kelly_full=f_full,
                    kelly_quarter=f_q, remaining_daily=remaining,
                    reason="EV no positivo: no se sugiere stake")
    if f > cap_pick:
        f = cap_pick; reasons.append("tope 2% por pick")
    if f > remaining:
        f = remaining; reasons.append("tope 8% de exposición diaria")
    unit_size = bankroll * (unit_pct / 100.0)
    stake = bankroll * f
    units = (stake / unit_size) if unit_size else 0.0
    return dict(frac=round(f, 6), stake=round(stake, 2), units=round(units, 2),
                unit_size=round(unit_size, 2), capped=bool(reasons),
                kelly_full=round(f_full, 6), kelly_quarter=round(f_q, 6),
                remaining_daily=round(remaining, 6),
                reason=("; ".join(reasons) if reasons else None))
