import asyncio, time, httpx

_client: httpx.AsyncClient | None = None
_store: dict = {}
_locks: dict = {}
STATS = {"hits": 0, "misses": 0, "errors": 0}

def client():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=20, headers={"User-Agent": "apuestas-app/1.0 (+uso personal)"}, follow_redirects=True,
                                    limits=httpx.Limits(max_connections=20))
    return _client

_sem = asyncio.Semaphore(12)

async def get_json(url: str, ttl: int = 120, params: dict | None = None):
    """GET con caché TTL en memoria, dedupe de peticiones en vuelo y 'stale on error'. Devuelve None si falla y no hay caché."""
    key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    now = time.time()
    ent = _store.get(key)
    if ent and now - ent[0] < ttl:
        STATS["hits"] += 1
        return ent[1]
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        ent = _store.get(key)
        if ent and time.time() - ent[0] < ttl:
            STATS["hits"] += 1
            return ent[1]
        STATS["misses"] += 1
        for attempt in range(2):
            try:
                async with _sem:
                    r = await client().get(url, params=params)
                if r.status_code == 200:
                    data = r.json()
                    _store[key] = (time.time(), data)
                    return data
                if r.status_code in (400, 404):
                    break
            except Exception:
                await asyncio.sleep(0.4)
        STATS["errors"] += 1
        return ent[1] if ent else None   # stale si existe
