"""Lesiones: parseo ESPN, cubetas, seguimiento propio (línea base honesta) y 'regresa'."""
from server import injuries as I

def inj(name, status, aid=None, href=None, detail=None):
    a = dict(displayName=name, position=dict(abbreviation="G"))
    if aid: a["id"] = aid
    if href: a["links"] = [dict(href=href)]
    return dict(athlete=a, status=status, date="2026-10-30T00:00Z", details=dict(type=detail or "Knee", detail="Soreness", side="Left", returnDate="2026-11-20"), shortComment="Nota")

def league(statuses_by_team):
    return dict(injuries=[dict(id=t, displayName=f"Team{t}", injuries=[inj(*x) for x in xs]) for t, xs in statuses_by_team.items()])

def teams(n=6, extra=None):
    d = {str(i): [(f"P{i}", "Out", f"{i}00")] for i in range(1, n + 1)}
    if extra: d.update(extra)
    return d

def test_bucket_and_status():
    assert I.bucket("Out") == "out" and I.bucket("Injured Reserve") == "out" and I.bucket("Suspension") == "out"
    assert I.bucket("Doubtful") == "doubt" and I.bucket("Questionable") == "dtd" and I.bucket("Day-To-Day") == "dtd"
    assert I.bucket("Active") is None and I.bucket("") == "dtd" or I.bucket("") is None
    assert I.status_es("Questionable") == "Cuestionable" and I.status_es("Out") == "Baja"

def test_pid_from_link_when_no_id():
    assert I._pid(dict(links=[dict(href="https://www.espn.com/nfl/player/_/id/4685503/foo")], displayName="X")) == "4685503"
    assert I._pid(dict(id=7)) == "7" and I._pid(dict(displayName="Ab C.")) == "n:abc"

def test_parse_filters_active_and_unspecified_detail():
    d = dict(injuries=[dict(id=1, displayName="T", injuries=[inj("A", "Active", "1"), inj("B", "Out", "2"), dict(athlete=dict(id=3, displayName="C"), status="Questionable", details=dict(type="Not Specified"))])])
    es = I.parse_league(d)["1"]["entries"]
    assert [e["name"] for e in es] == ["B", "C"] and es[1]["detail"] is None and es[0]["ret"] == "2026-11-20"
    assert I.counts(es) == dict(out=1, doubt=0, dtd=1)

def test_first_run_is_baseline_no_events(db):
    by = I.parse_league(league(teams()))
    I._last_track.clear()
    assert I.track("nba", by, now=1_000_000) == 0
    assert I.tracking_since("nba") == 1_000_000
    assert I.returning("nba", "1", now=1_000_100) == []

def test_partial_response_infers_nothing(db):
    I._last_track.clear()
    assert I.track("nba", I.parse_league(league(teams(3))), now=1_000_000) == 0
    assert I.tracking_since("nba") is None

def test_leaving_report_is_return_then_reappearing_cancels(db):
    I._last_track.clear()
    I.track("nba", I.parse_league(league(teams())), now=1_000_000)
    # P1 sale del reporte -> regresa
    I._last_track.clear()
    n = I.track("nba", I.parse_league(league({k: v for k, v in teams().items() if k != "1"} | {"1": []})), now=1_001_000)
    assert n == 1
    r = I.returning("nba", "1", now=1_002_000)
    assert len(r) == 1 and r[0]["name"] == "P1" and r[0]["kind"] == "salio" and r[0]["old"] == "Baja"
    # ventana de 10 días
    assert I.returning("nba", "1", days=10, now=1_001_000 + 11 * 86400) == []
    # vuelve a aparecer -> ya no se considera regreso
    I._last_track.clear()
    I.track("nba", I.parse_league(league(teams())), now=1_003_000)
    assert I.returning("nba", "1", now=1_004_000) == []

def test_status_improvement_is_return_and_worsening_is_not(db):
    I._last_track.clear()
    base = teams(extra={"1": [("P1", "Out", "100"), ("PX", "Questionable", "900")]})
    I.track("nba", I.parse_league(league(base)), now=1_000_000)
    I._last_track.clear()
    new = teams(extra={"1": [("P1", "Questionable", "100"), ("PX", "Out", "900")]})
    I.track("nba", I.parse_league(league(new)), now=1_001_000)
    r = {x["name"]: x for x in I.returning("nba", "1", now=1_002_000)}
    assert "P1" in r and r["P1"]["kind"] == "mejora" and r["P1"]["new"] == "Cuestionable" and "PX" not in r

def test_team_payload_orders_out_first_and_flags_key():
    es = [dict(I._entry(inj("Z", "Questionable", "1"))), dict(I._entry(inj("A", "Out", "2")))]
    p = I.team_payload("nba", "1", es, key_ids={"1"})
    assert [e["name"] for e in p["entries"]] == ["A", "Z"] and p["entries"][1]["key"] and p["counts"]["out"] == 1
