import os, sys, json, tempfile, pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

def fixture(name):
    with open(os.path.join(FIX, name)) as f: return json.load(f)

@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Base SQLite temporal y limpia (no toca data/history.db)."""
    from server import history, record
    p = str(tmp_path / "t.db")
    monkeypatch.setenv("APUESTAS_DB", p)
    monkeypatch.setattr(history, "_conn", None); monkeypatch.setattr(history, "PATH", None)
    record.reset_for_tests()
    yield p
    try:
        if history._conn: history._conn.close()
    except Exception: pass
    history._conn = None; record.reset_for_tests()
