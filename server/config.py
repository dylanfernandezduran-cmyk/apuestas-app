"""Configuración de deportes/ligas. Todas las fuentes son públicas y sin llave."""
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
MLB_API = "https://statsapi.mlb.com/api/v1"

# league key -> dict
LEAGUES = {
    "mlb": dict(path="baseball/mlb", family="baseball", name="MLB", sport="mlb", days=3),
    "nfl": dict(path="football/nfl", family="football", name="NFL", sport="nfl", days=7),
    "nba": dict(path="basketball/nba", family="basketball", name="NBA", sport="nba", days=3),
    "nhl": dict(path="hockey/nhl", family="hockey", name="NHL", sport="nhl", days=3),
    "atp": dict(path="tennis/atp", family="tennis", name="ATP", sport="tenis", days=0),
    "wta": dict(path="tennis/wta", family="tennis", name="WTA", sport="tenis", days=0),
    "mex.1": dict(path="soccer/mex.1", family="soccer", name="Liga MX", sport="futbol", days=7),
    "eng.1": dict(path="soccer/eng.1", family="soccer", name="Premier League", sport="futbol", days=7),
    "esp.1": dict(path="soccer/esp.1", family="soccer", name="LaLiga", sport="futbol", days=7),
    "ita.1": dict(path="soccer/ita.1", family="soccer", name="Serie A", sport="futbol", days=7),
    "ger.1": dict(path="soccer/ger.1", family="soccer", name="Bundesliga", sport="futbol", days=7),
    "uefa.champions": dict(path="soccer/uefa.champions", family="soccer", name="Champions League", sport="futbol", days=7),
}

SPORTS = [
    dict(key="mlb", name="MLB", emoji="⚾", leagues=["mlb"]),
    dict(key="nfl", name="NFL", emoji="🏈", leagues=["nfl"]),
    dict(key="nba", name="NBA", emoji="🏀", leagues=["nba"]),
    dict(key="nhl", name="NHL", emoji="🏒", leagues=["nhl"]),
    dict(key="tenis", name="Tenis", emoji="🎾", leagues=["atp", "wta"]),
    dict(key="futbol", name="Fútbol", emoji="⚽", leagues=["mex.1", "eng.1", "esp.1", "ita.1", "ger.1", "uefa.champions"]),
]

# Parámetros del modelo por familia (supuestos a priori, documentados en README)
FAMILY = {
    #            HFA prior, w(HFA), sigma margen, sigma total, k (shrink juegos), n_full
    "football":   dict(hfa=1.8, hfa_w=60, sigma=13.5, tsigma=10.5, k=6,  n_full=8),
    "basketball": dict(hfa=2.3, hfa_w=100, sigma=12.5, tsigma=18.0, k=12, n_full=20),
    "hockey":     dict(hfa=0.20, hfa_w=100, sigma=2.35, tsigma=2.40, k=14, n_full=20),
    "baseball":   dict(hfa=0.25, hfa_w=200, sigma=4.30, tsigma=4.50, k=40, n_full=60),
}
SOCCER = dict(home_prior=1.50, away_prior=1.20, prior_w=10, k=5, n_full=10)
EDGE_PICK = 3.0   # puntos porcentuales para PICK
EDGE_LEAN = 1.0   # puntos porcentuales para lean ligero
MIN_EV_MARGIN = 0.02  # margen de seguridad para "precio máximo"
TZ = "America/Mexico_City"
