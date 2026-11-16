"""Huella estable del sitio estático: ignora marcas de tiempo para no redesplegar si los datos no cambiaron."""
import hashlib, json, os

VOLATILE_KEYS = {"built", "now", "seconds", "fetched", "fetched_at", "generated_at", "as_of", "updated"}

def strip_volatile(obj):
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items() if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj

def content_hash(site_dir):
    h = hashlib.sha256()
    data = os.path.join(site_dir, "data")
    files = []
    for root, _, fns in os.walk(data):
        for fn in fns:
            if not fn.endswith(".json") or fn == "build.json":
                continue
            files.append(os.path.join(root, fn))
    for path in sorted(files):
        rel = os.path.relpath(path, site_dir).replace("\\", "/")
        raw = open(path, "rb").read()
        try:
            body = json.dumps(strip_volatile(json.loads(raw)), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        except Exception:
            body = raw
        h.update(rel.encode())
        h.update(b"\0")
        h.update(body)
        h.update(b"\n")
    return h.hexdigest()
