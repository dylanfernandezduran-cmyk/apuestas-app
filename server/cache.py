import asyncio, json, os, shutil, subprocess, time, httpx

_client: httpx.AsyncClient | None = None
_store: dict = {}
_locks: dict = {}
STATS = {"hits": 0, "misses": 0, "errors": 0, "curl": 0, "stale_budget": 0, "by_host": {}}
_curl_until = 0.0     # hasta cuándo usar curl en vez de httpx (ESPN/Akamai a veces responde 403 a la huella TLS de Python)
CURL_RETRY_S = 600
_budget_used: dict = {}

# Techos por proceso (un build de Pages). Si se acaba el cupo se sirve caché vieja; no se inventa.
# Open-Meteo gratis: 10_000/día, 5_000/h, 600/min (por IP; los runners de GitHub las comparten).
# Action Network y Pinnacle guest no publican cupo: conservamos un techo bajo por build.
def _host(url):
    try:
        return httpx.URL(url).host or ""
    except Exception:
        return ""

def _budget_of(host):
    defaults = {
        "api.actionnetwork.com": int(os.environ.get("BUDGET_AN", "40")),
        "guest.api.arcadia.pinnacle.com": int(os.environ.get("BUDGET_PIN", "80")),
        "api.open-meteo.com": int(os.environ.get("BUDGET_OM", "40")),
        "geocoding-api.open-meteo.com": int(os.environ.get("BUDGET_GEO", "30")),
    }
    return defaults.get(host)

def _host_stat(host, field, n=1):
    h = STATS["by_host"].setdefault(host or "?", {"hits": 0, "misses": 0, "errors": 0})
    h[field] = h.get(field, 0) + n

def load_store(path):
    """Restaura la caché HTTP de un JSON (rama estado) para builds incrementales."""
    if not path or not os.path.isfile(path):
        return 0
    try:
        blob = json.load(open(path, encoding="utf-8"))
        items = blob.get("items") if isinstance(blob, dict) else None
        if not isinstance(items, dict):
            return 0
        n = 0
        now = time.time()
        for k, ent in items.items():
            if not isinstance(ent, (list, tuple)) or len(ent) < 2:
                continue
            ts, data = ent[0], ent[1]
            try:
                ts = float(ts)
            except (TypeError, ValueError):
                continue
            if now - ts > 36 * 3600:
                continue
            _store[k] = (ts, data)
            n += 1
        return n
    except Exception:
        return 0

def dump_store(path, max_bytes=8_000_000):
    """Guarda la caché HTTP recortada (más recientes primero) para el siguiente build."""
    if not path:
        return 0
    items = sorted(_store.items(), key=lambda kv: kv[1][0], reverse=True)
    out = {}
    raw = b"{}"
    for k, (ts, data) in items:
        out[k] = [ts, data]
        raw = json.dumps({"v": 1, "items": out}, ensure_ascii=False, separators=(",", ":")).encode()
        if len(raw) > max_bytes:
            out.pop(k)
            raw = json.dumps({"v": 1, "items": out}, ensure_ascii=False, separators=(",", ":")).encode()
            break
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    open(path, "wb").write(raw)
    return len(out)

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
        _host_stat(_host(url), "hits")
        return ent[1]
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        ent = _store.get(key)
        if ent and time.time() - ent[0] < ttl:
            STATS["hits"] += 1
            _host_stat(_host(url), "hits")
            return ent[1]
        host = _host(url)
        cap = _budget_of(host)
        if cap is not None and _budget_used.get(host, 0) >= cap:
            STATS["stale_budget"] += 1
            _host_stat(host, "errors")
            return ent[1] if ent else None
        STATS["misses"] += 1
        _host_stat(host, "misses")
        if cap is not None:
            _budget_used[host] = _budget_used.get(host, 0) + 1
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
