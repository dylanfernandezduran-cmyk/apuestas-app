"""Liquidación pura: todos los mercados, líneas de cuarto, pushes, tenis (juegos/sets)."""
from server.grading import settle, settle_line

def R(h, a, **k): return dict(home=h, away=a, **k)
def T(sets):
    """sets: [(juegos_local, juegos_visita), …] -> res de tenis."""
    sh = sum(1 for x, y in sets if x > y); sa = sum(1 for x, y in sets if y > x)
    return dict(home=sh, away=sa, gh=sum(x for x, _ in sets), ga=sum(y for _, y in sets), sh=sh, sa=sa)

def test_ml():
    assert settle("ml", "home", None, R(100, 90)) == "GANADO"
    assert settle("ml", "away", None, R(100, 90)) == "PERDIDO"
    assert settle("ml", "away", None, R(90, 100)) == "GANADO"

def test_ml_tie_two_way_is_push():             # NFL empate: devolución
    assert settle("ml", "home", None, R(20, 20)) == "PUSH"
    assert settle("ml", "away", None, R(20, 20)) == "PUSH"

def test_1x2_soccer():
    assert settle("ml", "draw", None, R(1, 1), three_way=True) == "GANADO"
    assert settle("ml", "draw", None, R(2, 1), three_way=True) == "PERDIDO"
    assert settle("ml", "home", None, R(1, 1), three_way=True) == "PERDIDO"   # en 1X2 el empate pierde (no es push)
    assert settle("ml", "home", None, R(2, 1), three_way=True) == "GANADO"
    assert settle("ml", "draw", None, R(1, 1)) is None                       # 3-way fuera de fútbol: no se adivina

def test_double_chance():
    assert settle("dc", "1X", None, R(1, 1)) == "GANADO" and settle("dc", "1X", None, R(0, 1)) == "PERDIDO"
    assert settle("dc", "X2", None, R(1, 1)) == "GANADO" and settle("dc", "X2", None, R(2, 1)) == "PERDIDO"
    assert settle("dc", "12", None, R(1, 1)) == "PERDIDO" and settle("dc", "12", None, R(2, 1)) == "GANADO"

def test_spread_half_and_whole():
    # local 112-90 → margen +22 para local
    assert settle("spread", "home", -21.5, R(112, 90)) == "GANADO"
    assert settle("spread", "home", -22.5, R(112, 90)) == "PERDIDO"
    assert settle("spread", "home", -22, R(112, 90)) == "PUSH"
    assert settle("spread", "away", 22, R(112, 90)) == "PUSH"
    assert settle("spread", "away", 22.5, R(112, 90)) == "GANADO"
    assert settle("spread", "away", 21.5, R(112, 90)) == "PERDIDO"

def test_spread_missing_line_is_none():
    assert settle("spread", "home", None, R(1, 0)) is None and settle("total", "over", None, R(1, 0)) is None

def test_asian_quarter_lines():
    # fútbol 2-1 (margen +1 local): -0.75 → gana -0.5 y push? (−0.5: gana, −1: push) = medio ganado
    assert settle("spread", "home", -0.75, R(2, 1)) == "MEDIO_GANADO"
    assert settle("spread", "home", -1.25, R(2, 1)) == "MEDIO_PERDIDO"   # -1 push, -1.5 pierde
    assert settle("spread", "home", -0.25, R(1, 1)) == "MEDIO_PERDIDO"   # 0 push, -0.5 pierde
    assert settle("spread", "home", 0.25, R(1, 1)) == "MEDIO_GANADO"
    assert settle("spread", "home", -0.25, R(2, 0)) == "GANADO"
    assert settle("spread", "home", -1.75, R(1, 0)) == "PERDIDO"
    assert settle("spread", "away", 0.75, R(1, 1)) == "GANADO"
    # totales con cuarto: over 2.75 = mitad a 2.5 + mitad a 3
    assert settle("total", "over", 2.75, R(2, 1)) == "MEDIO_GANADO"      # 3 goles: 2.5 gana, 3.0 push
    assert settle("total", "under", 2.75, R(2, 1)) == "MEDIO_PERDIDO"
    assert settle("total", "over", 2.25, R(1, 1)) == "MEDIO_PERDIDO"     # 2 goles: 2.0 push, 2.5 pierde
    assert settle("total", "under", 2.25, R(1, 1)) == "MEDIO_GANADO"
    assert settle("total", "over", 2.25, R(2, 1)) == "GANADO"

def test_totals():
    assert settle("total", "over", 201.5, R(112, 90)) == "GANADO"        # 202 pts
    assert settle("total", "over", 202, R(112, 90)) == "PUSH"
    assert settle("total", "under", 202, R(112, 90)) == "PUSH"
    assert settle("total", "under", 203.5, R(112, 90)) == "GANADO"
    assert settle("total", "over", 210.5, R(112, 90)) == "PERDIDO"

def test_hockey_shootout_total_excludes_shootout_goal():
    res = dict(home=5, away=4, home_t=4, away_t=4)       # 5-4 en penales; goles reales 4-4
    assert settle("total", "over", 7.5, res) == "GANADO"
    assert settle("total", "over", 8.5, res) == "PERDIDO"   # con el gol de la tanda serían 9
    assert settle("total", "under", 8, res) == "PUSH"
    assert settle("ml", "home", None, res) == "GANADO"
    assert settle("spread", "away", 1.5, res) == "GANADO"   # puck line +1.5, derrota por 1

# ---------------- tenis
def test_tennis_ml_no_draw():
    assert settle("ml", "home", None, T([(6, 4), (6, 3)])) == "GANADO"
    assert settle("ml", "away", None, T([(6, 4), (6, 3)])) == "PERDIDO"

def test_tennis_games_handicap_and_total():
    r = T([(4, 6), (6, 3), (6, 3)])                    # local gana 2-1 en sets; juegos 16-12 (margen +4)
    assert (r["gh"], r["ga"]) == (16, 12)
    assert settle("spread", "home", -3.5, r) == "GANADO"
    assert settle("spread", "home", -4.5, r) == "PERDIDO"
    assert settle("spread", "home", -4, r) == "PUSH"
    assert settle("spread", "away", 3.5, r) == "PERDIDO"
    assert settle("spread", "away", 4.5, r) == "GANADO"
    assert settle("total", "over", 28.5, r) == "PERDIDO"       # 28 juegos
    assert settle("total", "over", 22.5, r) == "GANADO"
    assert settle("total", "under", 28, r) == "PUSH"
    assert settle("total", "under", 28.5, r) == "GANADO"

def test_tennis_games_use_games_not_sets():
    r = T([(6, 3), (6, 4)])        # 2-0 en sets, 12-7 juegos
    # el hándicap de JUEGOS -3.5 debe usar 12-7=+5 (gana); con sets (+2) ganaría -1.5 pero perdería -3.5
    assert settle("spread", "home", -3.5, r) == "GANADO"
    assert settle("sspread", "home", -3.5, r) == "PERDIDO"
    assert settle("sspread", "home", -1.5, r) == "GANADO"

def test_tennis_sets_markets():
    r = T([(6, 3), (3, 6), (7, 6)])     # 2-1 sets
    assert settle("stotal", "over", 2.5, r) == "GANADO"          # 3 sets
    assert settle("stotal", "under", 2.5, r) == "PERDIDO"
    assert settle("sspread", "away", 1.5, r) == "GANADO"          # el perdedor +1.5 sets
    assert settle("sspread", "home", -1.5, r) == "PERDIDO"        # ganó 2-1: no cubre -1.5
    r2 = T([(6, 3), (6, 4)])
    assert settle("stotal", "under", 2.5, r2) == "GANADO"
    assert settle("sspread", "home", -1.5, r2) == "GANADO"
    assert settle("sspread", "away", 1.5, r2) == "PERDIDO"

def test_sets_markets_not_for_team_sports():
    assert settle("sspread", "home", 1.5, R(1, 0)) is None and settle("stotal", "over", 2.5, R(1, 0)) is None

def test_unknown_market_is_none():
    assert settle("prop", "home", 1, R(1, 0)) is None
