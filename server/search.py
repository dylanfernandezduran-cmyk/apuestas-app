"""Buscador del inicio: juegos, equipos, jugadores (tenis) y ligas/torneos sobre los juegos ya cargados de todas las ligas."""
import unicodedata

ALIASES = {"mlb": "beisbol baseball", "nfl": "futbol americano football nfl", "nba": "basquetbol basketball baloncesto", "nhl": "hockey",
           "tenis": "tennis atp wta", "futbol": "soccer futbol"}
STATE_RANK = {"in": 0, "pre": 1, "post": 2}

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace(".", " ").replace("-", " ").split())

def tokens(q):
    return [t for t in norm(q).split() if t]

def _hit(toks, hay):
    """Cada palabra buscada debe ser el comienzo de alguna palabra del texto (así 'ab' no encuentra 'Elizabeth')."""
    words = hay.split()
    return bool(toks) and all(any(w.startswith(t) for w in words) for t in toks)

def _side(t):
    return dict(name=t.get("name"), short=t.get("short"), logo=t.get("logo"), score=t.get("score"), sets=t.get("sets"))

def search(q, games_by_league, leagues, sports, limit_games=8, limit_teams=4, limit_leagues=3):
    """games_by_league: {liga: [juego]}; leagues: config LEAGUES; sports: config SPORTS. Devuelve dict(q, leagues, teams, games)."""
    toks = tokens(q)
    out = dict(q=q, leagues=[], teams=[], games=[])
    if not toks or sum(len(t) for t in toks) < 2:
        return out
    emoji = {s["key"]: s["emoji"] for s in sports}
    # ligas / torneos / deportes
    for key, cfg in leagues.items():
        gs = games_by_league.get(key) or []
        hay = norm(f"{cfg['name']} {key} {cfg['sport']} {ALIASES.get(cfg['sport'], '')}")
        tour = {norm(g.get("note") or "").split(" round")[0] for g in gs if g.get("note")}
        tour_hit = next((g.get("note") for g in gs if g.get("note") and _hit(toks, norm(g["note"]))), None)
        if _hit(toks, hay) or tour_hit:
            out["leagues"].append(dict(key=key, sport=cfg["sport"], name=cfg["name"] if not tour_hit or _hit(toks, hay) else (tour_hit.split(" · ")[0] or cfg["name"]),
                                       emoji=emoji.get(cfg["sport"], ""), n=len(gs), sub=("Torneo · " + cfg["name"]) if tour_hit and not _hit(toks, hay) else None))
    out["leagues"] = out["leagues"][:limit_leagues]
    # juegos y equipos/jugadores
    teams, games = {}, []
    for lg, gs in games_by_league.items():
        cfg = leagues.get(lg) or {}
        for g in gs or []:
            parts = [g.get(sd) or {} for sd in ("home", "away")]
            names = [norm(f"{p.get('name')} {p.get('short')} {p.get('abbr') or ''}") for p in parts]
            ghay = " ".join(names) + " " + norm(f"{g.get('league_name')} {g.get('note') or ''} {cfg.get('sport', '')} {ALIASES.get(cfg.get('sport'), '')}")
            full = norm(" ".join(f"{p.get('name')}" for p in parts))
            matched_team = False
            for p, nm in zip(parts, names):
                if _hit(toks, nm):
                    matched_team = True
                    k = (lg, p.get("id") or p.get("name"))
                    cur = teams.get(k)
                    rank = (STATE_RANK.get(g.get("state"), 3), g.get("date") or "")
                    if cur is None or rank < cur["_r"]:
                        teams[k] = dict(_r=rank, name=p.get("name"), logo=p.get("logo"), league=lg, league_name=g.get("league_name"), sport=g.get("sport"),
                                        game_id=g.get("id"), state=g.get("state"), date=g.get("date"), opp=(parts[1] if p is parts[0] else parts[0]).get("short") or (parts[1] if p is parts[0] else parts[0]).get("name"))
            if matched_team or _hit(toks, ghay) or _hit(toks, full):
                games.append(dict(_r=(STATE_RANK.get(g.get("state"), 3), g.get("date") or ""), id=g.get("id"), league=lg, league_name=g.get("league_name"), sport=g.get("sport"),
                                  state=g.get("state"), status=g.get("status"), date=g.get("date"), home=_side(g.get("home") or {}), away=_side(g.get("away") or {}),
                                  direct=matched_team))
    games.sort(key=lambda x: (not x["direct"], x["_r"]))
    out["games"] = [{k: v for k, v in x.items() if k != "_r"} for x in games[:limit_games]]
    tl = sorted(teams.values(), key=lambda x: x["_r"])[:limit_teams]
    out["teams"] = [{k: v for k, v in x.items() if k != "_r"} for x in tl]
    return out
