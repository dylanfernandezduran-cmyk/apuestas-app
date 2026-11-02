"""Clima (Open-Meteo): hora de juego, techos, notas neutrales y que NUNCA se invente (sin dato -> 'sin_dato')."""
import asyncio
from datetime import datetime, timedelta, timezone
from server import weather as W

def hourly(n=48, start="2026-11-05T00:00"):
    base = datetime.fromisoformat(start)
    t = [(base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(n)]
    return dict(time=t, temperature_2m=[10 + i for i in range(n)], apparent_temperature=[9] * n, relative_humidity_2m=[80] * n, precipitation_probability=[20] * n,
                precipitation=[0.0] * n, weather_code=[3] * n, wind_speed_10m=[12.0] * n, wind_direction_10m=[225] * n, wind_gusts_10m=[20.0] * n)

def test_pick_hour_rounds_and_bounds():
    h = hourly(48, "2026-11-05T00:00")
    d = lambda hh, mm: datetime(2026, 11, 5, hh, mm, tzinfo=timezone.utc)
    assert W.pick_hour(h, d(1, 10)) == h["time"].index("2026-11-05T01:00")
    assert W.pick_hour(h, d(1, 40)) == h["time"].index("2026-11-05T02:00")
    assert W.pick_hour(h, datetime(2027, 1, 1, tzinfo=timezone.utc)) is None and W.pick_hour({}, d(1, 0)) is None

def test_build_units_and_direction():
    w = W.build(hourly(), 5, elevation=100)
    assert w["temp_c"] == 15 and w["wind_kmh"] == 12.0 and w["wind_from"] == "SO" and w["text"] == "Nublado" and w["precip_prob"] == 20
    assert W.cardinal(0) == "N" and W.cardinal(90) == "E" and W.cardinal(None) is None

def test_roof():
    assert W.roof("Lucas Oil Stadium", None) == "retractil" and W.roof("Ford Field", None) == "techado"
    assert W.roof("Anything", True) == "techado" and W.roof("Lumen Field", False) is None and W.roof(None, None) is None

def test_notes_thresholds_are_generic_and_neutral():
    calm = dict(wind_kmh=10, gust_kmh=15, precip_prob=10, precip_mm=0, temp_c=15, elevation_m=100)
    assert W.notes(calm, "football") == []
    assert len(W.notes(dict(calm, wind_kmh=30), "football")) == 1 and len(W.notes(dict(calm, gust_kmh=45), "soccer")) == 1
    assert any("Lluvia" in n and "retraso" in n for n in W.notes(dict(calm, precip_prob=60), "baseball"))
    assert not any("retraso" in n for n in W.notes(dict(calm, precip_prob=60), "soccer"))
    assert any("Frío" in n for n in W.notes(dict(calm, temp_c=-2), "football")) and any("Calor" in n for n in W.notes(dict(calm, temp_c=34), "baseball"))
    assert any("Altitud" in n for n in W.notes(dict(calm, elevation_m=2240), "soccer"))

def test_choose_geo_matches_state_and_country():
    rs = [dict(name="Springfield", admin1="Illinois", country_code="US", latitude=1, longitude=1), dict(name="Springfield", admin1="Missouri", country_code="US", latitude=2, longitude=2)]
    assert W.choose_geo(rs, "MO", "USA")["latitude"] == 2
    assert W.choose_geo([dict(country_code="GB", admin1="England", latitude=3, longitude=3)], None, "Spain") is None
    assert W.choose_geo([], "MO", "USA") is None

def run(c): return asyncio.run(c)

def test_game_weather_statuses(monkeypatch):
    when = datetime(2026, 11, 5, 3, 0, tzinfo=timezone.utc)
    assert run(W.game_weather({}, "basketball", when))["status"] == "no_aplica"
    assert run(W.game_weather(dict(venue="Ford Field"), "football", when))["status"] == "techado"
    g = dict(venue="M&T Bank Stadium", venue_city="Baltimore", venue_state="MD", venue_country="USA")
    async def nogeo(*a): return None
    monkeypatch.setattr(W, "geocode", nogeo)
    r = run(W.game_weather(g, "football", when)); assert r["status"] == "sin_dato" and "reason" in r
    async def geo(*a): return (39.3, -76.6, 10)
    async def nofc(*a): return None
    monkeypatch.setattr(W, "geocode", geo); monkeypatch.setattr(W, "forecast", nofc)
    assert run(W.game_weather(g, "football", when))["status"] == "sin_dato"
    async def fc(*a): return dict(hourly=hourly(48, "2026-11-05T00:00"), elevation=12)
    monkeypatch.setattr(W, "forecast", fc)
    r = run(W.game_weather(g, "football", when))
    assert r["status"] == "ok" and r["source"] == "Open-Meteo" and r["temp_c"] == 13 and r["at"] == "2026-11-05T03:00Z"
    assert run(W.game_weather(g, "football", datetime(2026, 12, 25, tzinfo=timezone.utc)))["status"] == "sin_dato"
    assert run(W.game_weather(dict(g, venue="Rogers Centre"), "baseball", when))["status"] == "retractil"
    assert run(W.game_weather(g, "football", None))["status"] == "sin_dato"
