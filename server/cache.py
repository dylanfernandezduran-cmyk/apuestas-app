import asyncio, json, shutil, subprocess, time, httpx

_client: httpx.AsyncClient | None = None
_store: dict = {}
_locks: dict = {}
STATS = {"hits": 0, "misses": 0, "errors": 0, "curl": 0}
_curl_until = 0.0     # hasta cuándo usar curl en vez de httpx (ESPN/Akamai a veces responde 403 a la huella TLS de Python)
CURL_RETRY_S = 600

def client():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=20, headers={"User-Agent": "apuestas-app/1.0 (+uso personal)"}, follow_redirects=True,
                                    limits=httpx.Limits(max_connections=20))
    return _client

_sem = asyncio.Semaphore(12)

def _key(url, params=None):
    return url + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))

def fetched_at(url, params=None):
    ent = _store.get(_key(url, params))
    return ent[0] if ent else None

def _curl_raw(full_url, headers, accept="application/json"):
    exe = shutil.which("curl") or shutil.which("curl.exe")
    if not exe: return None
    args = [exe, "-sS", "-L", "--compressed", "--max-time", "20", "-H", f"Accept: {accept}", "-w", "\n%{http_code}"]
    for k, v in (headers or {}).items(): args += ["-H", f"{k}: {v}"]
    r = subprocess.run(args + [full_url], capture_output=True, timeout=30)
    body, _, code = r.stdout.rpartition(b"\n")
    if code.strip() != b"200": return None
    return body

def _curl_run(full_url, headers):
    body = _curl_raw(full_url, headers)
    return None if body is None else json.loads(body)

async def fetch_bytes(url: str, headers: dict | None = None):
    """GET binario (imágenes). Devuelve (bytes, content_type) o None. Mismo respaldo con curl si ESPN/Akamai da 403 a httpx."""
    blocked = time.time() < _curl_until
    if not blocked:
        try:
            async with _sem:
                r = await client().get(url, headers=headers)
            if r.status_code == 200 and r.content:
                return r.content, r.headers.get("content-type", "").split(";")[0].strip()
            if r.status_code != 403:
                return None
            blocked = True
        except Exception:
            return None
    try:
        async with _sem:
            body = await asyncio.to_thread(_curl_raw, url, headers, "image/*")
    except Exception:
        return None
    if not body: return None
    STATS["curl"] += 1
    return body, _sniff(body)

def _sniff(b: bytes):
    if b[:8] == b"\x89PNG\r\n\x1a\n": return "image/png"
    if b[:3] == b"\xff\xd8\xff": return "image/jpeg"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return "image/webp"
    if b[:6] in (b"GIF87a", b"GIF89a"): return "image/gif"
    return ""

async def _curl_get(url, params=None, headers=None):
    """Respaldo cuando httpx recibe 403 (bloqueo por huella TLS de Python): mismo GET público con curl del sistema. None si falla."""
    try:
        full = str(httpx.URL(url).copy_merge_params(params or {}))
        return await asyncio.to_thread(_curl_run, full, headers)
    except Exception:
        return None

async def get_json(url: str, ttl: int = 120, params: dict | None = None, headers: dict | None = None):
    """GET con caché TTL en memoria, dedupe de peticiones en vuelo y 'stale on error'. Devuelve None si falla y no hay caché."""
    key = _key(url, params)
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
        global _curl_until
        blocked = False
        if time.time() < _curl_until:
            blocked = True
        else:
            for attempt in range(2):
                try:
                    async with _sem:
                        r = await client().get(url, params=params, headers=headers)
                    if r.status_code == 200:
                        data = r.json()
                        _store[key] = (time.time(), data)
                        return data
                    if r.status_code == 403:
                        blocked = True; break
                    if r.status_code in (400, 404):
                        break
                except Exception:
                    await asyncio.sleep(0.4)
        if blocked:
            async with _sem:
                data = await _curl_get(url, params, headers)
            if data is not None:
                _curl_until = time.time() + CURL_RETRY_S; STATS["curl"] += 1
                _store[key] = (time.time(), data)
                return data
            _curl_until = 0.0
        STATS["errors"] += 1
        return ent[1] if ent else None   # stale si existe
