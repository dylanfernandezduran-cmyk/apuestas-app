"""Proxy + caché de imágenes de ESPN (logos de equipos, fotos de jugadores de tenis).
Por qué por el servidor: ESPN/Akamai a veces bloquea la huella TLS de Python (se reutiliza el respaldo con curl de cache.py), el navegador
recibe imágenes ya reducidas (combiner de ESPN, w=48..128 en vez de PNG de 500px) con caché larga, y sólo se permiten hosts de imágenes de ESPN."""
import asyncio, hashlib, os, tempfile, time
from urllib.parse import urlsplit, quote
from .cache import fetch_bytes

ALLOWED_HOSTS = {"a.espncdn.com", "s.espncdn.com"}
ALLOWED_PREFIXES = ("/i/",)
WIDTHS = (32, 48, 64, 96, 128)
NEG_TTL = 600           # fallo (404/red): no reintentar en 10 min -> el frontend muestra iniciales
MEM_MAX = 400
_mem: dict = {}         # key -> (bytes, content_type)
_neg: dict = {}         # key -> ts
_locks: dict = {}

def _dir():
    for p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "img"), os.path.join(tempfile.gettempdir(), "apuestas_img")):
        try:
            os.makedirs(p, exist_ok=True)
            return p
        except Exception:
            continue
    return None

def validate(u: str):
    """Devuelve (host, path) si la URL es una imagen de ESPN permitida; None si no."""
    try:
        s = urlsplit(u or "")
    except Exception:
        return None
    if s.scheme != "https" or (s.hostname or "") not in ALLOWED_HOSTS or s.username or s.port:
        return None
    if not s.path.startswith(ALLOWED_PREFIXES) or ".." in s.path or not s.path.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        return None
    return s.hostname, s.path

def clamp_w(w):
    try: w = int(w)
    except Exception: return 64
    return min(WIDTHS, key=lambda x: abs(x - w))

def upstream_url(path, w):
    return f"https://a.espncdn.com/combiner/i?img={quote(path, safe='/')}&w={w}"

def _key(path, w):
    return hashlib.sha1(f"{path}|{w}".encode()).hexdigest()

_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}
_CT = {v: k for k, v in _EXT.items()}

def _disk_get(key):
    d = _dir()
    if not d: return None
    for ext, ct in _CT.items():
        f = os.path.join(d, f"{key}.{ext}")
        if os.path.exists(f):
            try:
                with open(f, "rb") as fh: return fh.read(), ct
            except Exception: return None
    return None

def _disk_put(key, body, ct):
    d = _dir()
    ext = _EXT.get(ct)
    if not d or not ext: return
    try:
        tmp = os.path.join(d, f"{key}.tmp{os.getpid()}")
        with open(tmp, "wb") as fh: fh.write(body)
        os.replace(tmp, os.path.join(d, f"{key}.{ext}"))
    except Exception:
        pass

async def get_image(u: str, w=64):
    """(bytes, content_type) o None. Memoria -> disco -> ESPN (httpx con respaldo curl)."""
    v = validate(u)
    if not v: return None
    w = clamp_w(w)
    key = _key(v[1], w)
    if key in _mem: return _mem[key]
    if time.time() - _neg.get(key, 0) < NEG_TTL: return None
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        if key in _mem: return _mem[key]
        hit = await asyncio.to_thread(_disk_get, key)
        if not hit:
            hit = await fetch_bytes(upstream_url(v[1], w))
            if hit and not (hit[1] or "").startswith("image/"): hit = None
            if hit and len(hit[0]) > 2_000_000: hit = None
            if hit: await asyncio.to_thread(_disk_put, key, *hit)
        _locks.pop(key, None)
        if not hit:
            _neg[key] = time.time()
            return None
        if len(_mem) >= MEM_MAX: _mem.pop(next(iter(_mem)))
        _mem[key] = hit
        return hit
