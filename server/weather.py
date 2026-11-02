"""Clima del estadio con Open-Meteo (gratis, sin llave) para deportes al aire libre (NFL, MLB, fútbol). Techados -> 'Techado' (no se consulta).
Sólo contexto: NO modifica el modelo."""
import time, re
from datetime import timedelta
from .cache import get_json
from . import history as H

GEO = "https://geocoding-api.open-meteo.com/v1/search"
FC = "https://api.open-meteo.com/v1/forecast"
OUTDOOR_FAMILIES = ("football", "baseball", "soccer")
# techo fijo (domo) o retráctil: dato público del estadio; ESPN trae `indoor` sólo para algunos. Si ESPN marca indoor=True se trata como techado.
RETRACTABLE = ("rogers centre", "chase field", "american family field", "minute maid park", "daikin park", "loandepot park", "globe life field",
               "at&t stadium", "lucas oil stadium", "state farm stadium", "nrg stadium", "mercedes-benz stadium")
FULL_ROOF = ("tropicana field", "caesars superdome", "ford field", "u.s. bank stadium", "allegiant stadium")
US_STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
             "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
             "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
             "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
             "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
             "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia", "ON": "Ontario"}
CC = {"usa": "US", "united states": "US", "mexico": "MX", "méxico": "MX", "england": "GB", "scotland": "GB", "wales": "GB", "united kingdom": "GB", "spain": "ES", "italy": "IT",
      "germany": "DE", "france": "FR", "portugal": "PT", "netherlands": "NL", "belgium": "BE", "turkey": "TR", "canada": "CA", "brazil": "BR", "argentina": "AR", "austria": "AT",
      "switzerland": "CH", "greece": "GR", "czech republic": "CZ", "poland": "PL", "ukraine": "UA", "serbia": "RS", "croatia": "HR", "denmark": "DK", "norway": "NO", "sweden": "SE",
      "scotland": "GB", "ireland": "IE", "israel": "IL", "azerbaijan": "AZ", "slovakia": "SK", "slovenia": "SI", "hungary": "HU", "romania": "RO", "bulgaria": "BG", "kazakhstan": "KZ"}
WMO = {0: ("☀️", "Despejado"), 1: ("🌤️", "Mayormente despejado"), 2: ("⛅", "Parcialmente nublado"), 3: ("☁️", "Nublado"), 45: ("🌫️", "Niebla"), 48: ("🌫️", "Niebla con escarcha"),
       51: ("🌦️", "Llovizna ligera"), 53: ("🌦️", "Llovizna"), 55: ("🌦️", "Llovizna intensa"), 56: ("🌧️", "Llovizna helada"), 57: ("🌧️", "Llovizna helada"),
       61: ("🌧️", "Lluvia ligera"), 63: ("🌧️", "Lluvia"), 65: ("🌧️", "Lluvia fuerte"), 66: ("🌧️", "Lluvia helada"), 67: ("🌧️", "Lluvia helada"),
       71: ("🌨️", "Nieve ligera"), 73: ("🌨️", "Nieve"), 75: ("❄️", "Nieve fuerte"), 77: ("🌨️", "Granizo fino"), 80: ("🌦️", "Chubascos ligeros"), 81: ("🌧️", "Chubascos"),
       82: ("⛈️", "Chubascos fuertes"), 85: ("🌨️", "Chubascos de nieve"), 86: ("🌨️", "Chubascos de nieve"), 95: ("⛈️", "Tormenta"), 96: ("⛈️", "Tormenta con granizo"), 99: ("⛈️", "Tormenta con granizo")}
CARD = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]

def cardinal(deg):
    return None if deg is None else CARD[int((deg % 360) / 22.5 + 0.5) % 16]

def roof(venue_name, indoor):
    """-> 'techado' | 'retractil' | None (al aire libre)."""
    n = (venue_name or "").lower()
    if indoor is True or any(k in n for k in FULL_ROOF): return "techado"
    if any(k in n for k in RETRACTABLE): return "retractil"
    return None

def notes(w, family):
    """Notas de contexto neutrales (umbrales generales; no son estadísticas del modelo)."""
    out = []
    ws, gu, pp, pr, t = w.get("wind_kmh"), w.get("gust_kmh"), w.get("precip_prob"), w.get("precip_mm"), w.get("temp_c")
    if (ws is not None and ws >= 25) or (gu is not None and gu >= 40):
        eff = {"football": "puede afectar pases largos y goles de campo/pateo", "baseball": "puede cambiar el vuelo de la bola (a favor o en contra según la dirección) y afectar totales",
               "soccer": "puede afectar pases largos, centros y tiros de lejos"}.get(family, "puede afectar el juego")
        out.append(f"💨 Viento fuerte ({ws:.0f} km/h{f', ráfagas {gu:.0f}' if gu else ''}): {eff}.")
    if (pp is not None and pp >= 50) or (pr is not None and pr >= 1):
        out.append(f"🌧️ Lluvia probable ({pp:.0f}%{f', {pr:.1f} mm' if pr else ''}): cancha/balón resbaloso" + ("; posible retraso o suspensión" if family == "baseball" else "") + ".")
    if t is not None and t <= 0: out.append(f"🥶 Frío extremo ({t:.0f} °C): puede afectar el manejo del balón y el pateo.")
    if t is not None and t >= 32: out.append(f"🥵 Calor ({t:.0f} °C): posible desgaste y ritmo más bajo en la segunda mitad.")
    if w.get("elevation_m") is not None and w["elevation_m"] >= 1500: out.append(f"⛰️ Altitud {w['elevation_m']:.0f} m: el aire es menos denso (bola/balón viaja más) y se resiente la resistencia.")
    return out

def pick_hour(hourly, when_utc):
    """Índice de la hora más cercana (UTC) en la serie horaria de Open-Meteo, o None si la fecha queda fuera del pronóstico."""
    times = hourly.get("time") or []
    if not times: return None
    target = when_utc.replace(minute=0, second=0, microsecond=0) + (timedelta(hours=1) if when_utc.minute >= 30 else timedelta())
    key = target.strftime("%Y-%m-%dT%H:00")
    return times.index(key) if key in times else None

def build(hourly, i, elevation=None):
    g = lambda k: (hourly.get(k) or [None] * (i + 1))[i]
    code = g("weather_code")
    ico, txt = WMO.get(code, ("", None)) if code is not None else ("", None)
    w = dict(temp_c=g("temperature_2m"), feels_c=g("apparent_temperature"), humidity=g("relative_humidity_2m"), wind_kmh=g("wind_speed_10m"), wind_dir=g("wind_direction_10m"),
             gust_kmh=g("wind_gusts_10m"), precip_prob=g("precipitation_probability"), precip_mm=g("precipitation"), code=code, icon=ico, text=txt, elevation_m=elevation)
    w["wind_from"] = cardinal(w["wind_dir"])
    return w

# ------------------------------------------------------------------ geocodificación (con caché persistente)
_geo_mem = {}
def _geo_db_get(k):
    try:
        c = H._open()
        with H._lock:
            c.execute("CREATE TABLE IF NOT EXISTS geo(k TEXT PRIMARY KEY, lat REAL, lon REAL, elev REAL, ts INTEGER)")
            r = c.execute("SELECT lat,lon,elev FROM geo WHERE k=?", (k,)).fetchone()
        return r
    except Exception: return None
def _geo_db_put(k, lat, lon, elev):
    try:
        c = H._open()
        with H._lock:
            c.execute("INSERT OR REPLACE INTO geo VALUES(?,?,?,?,?)", (k, lat, lon, elev, int(time.time()))); c.commit()
    except Exception: pass

def choose_geo(results, state, country):
    """Elige el resultado del geocodificador que coincide con estado/país de ESPN (si se dieron); si ninguno coincide devuelve None."""
    if not results: return None
    cc = CC.get((country or "").lower())
    st = US_STATES.get((state or "").upper(), state)
    best = None
    for idx, r in enumerate(results):
        sc = (2 if cc and r.get("country_code") == cc else 0) + (2 if st and (r.get("admin1") or "").lower() == st.lower() else 0)
        if best is None or sc > best[0]: best = (sc, r)
    return best[1] if best[0] > 0 or not (cc or st) else None

async def geocode(city, state, country):
    if not city: return None
    k = f"{city}|{state or ''}|{country or ''}".lower()
    if k in _geo_mem: return _geo_mem[k]
    r = _geo_db_get(k)
    if r: _geo_mem[k] = r; return r
    cands = [city] + ([city.split("-")[0].strip()] if "-" in city else [])
    for q in cands:
        d = await get_json(GEO, ttl=86400 * 30, params={"name": q, "count": 10, "language": "en", "format": "json"})
        g = choose_geo((d or {}).get("results"), state, country)
        if g:
            res = (g["latitude"], g["longitude"], g.get("elevation"))
            _geo_mem[k] = res; _geo_db_put(k, *res); return res
    return None

async def forecast(lat, lon):
    return await get_json(FC, ttl=1800, params=dict(latitude=round(lat, 3), longitude=round(lon, 3), timezone="UTC", forecast_days=16, past_days=2, wind_speed_unit="kmh",
        hourly="temperature_2m,apparent_temperature,relative_humidity_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m"))

async def game_weather(game, family, when_utc):
    """-> dict(status='ok'|'techado'|'retractil'|'no_aplica'|'sin_dato', ...). Siempre con 'source' y hora del dato."""
    if family not in OUTDOOR_FAMILIES: return dict(status="no_aplica")
    r = roof(game.get("venue"), game.get("indoor"))
    base = dict(venue=game.get("venue"), city=game.get("venue_city"), roof=r)
    if r == "techado": return dict(base, status="techado")
    if when_utc is None: return dict(base, status="sin_dato", reason="Sin hora de inicio")
    geo = await geocode(game.get("venue_city"), game.get("venue_state"), game.get("venue_country"))
    if not geo: return dict(base, status="sin_dato", reason="No se pudo ubicar el estadio (ESPN no trae ciudad o no se encontró en el geocodificador)")
    fc = await forecast(geo[0], geo[1])
    if not fc or not fc.get("hourly"): return dict(base, status="sin_dato", reason="Open-Meteo no respondió")
    i = pick_hour(fc["hourly"], when_utc)
    if i is None: return dict(base, status="sin_dato", reason="Fuera del rango del pronóstico (16 días)")
    w = build(fc["hourly"], i, fc.get("elevation", geo[2]))
    return dict(base, status=("retractil" if r == "retractil" else "ok"), source="Open-Meteo", at=fc["hourly"]["time"][i] + "Z", fetched=time.time(), notes=notes(w, family), **w)
