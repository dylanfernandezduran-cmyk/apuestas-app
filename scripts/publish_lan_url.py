"""Detecta la IPv4 LAN de esta máquina y escribe lan.json (para el banner de Pages).
Uso en la PC (o en el box vía Shell a la PC):
  python scripts/publish_lan_url.py
No cambia el adaptador ni el router. El hostname .local es el link estable;
este archivo solo publica la IP actual como respaldo en el build de Pages.
"""
from __future__ import annotations
import json, os, socket, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "lan.json")
PORT = int(os.environ.get("NRNM_PORT", "8765"))

def lan_ipv4() -> str | None:
    for probe in ("192.168.100.1", "8.8.8.8"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.3)
            s.connect((probe, 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                return ip
    except Exception:
        pass
    return None

def main():
    ip = lan_ipv4()
    host = (socket.gethostname() or "DESKTOP-NOG66RU").split(".")[0]
    local = f"http://{host}.local:{PORT}"
    by_ip = f"http://{ip}:{PORT}" if ip else None
    prev = {}
    if os.path.isfile(OUT):
        try: prev = json.load(open(OUT, encoding="utf-8"))
        except Exception: prev = {}
    doc = dict(
        ok=True,
        ip=ip,
        port=PORT,
        hostname=host,
        url_local=local,
        url_ip=by_ip,
        preferred=local,
        updated=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        note="url_local (.local) no cambia con DHCP; url_ip es respaldo",
    )
    changed = prev.get("ip") != ip or prev.get("url_local") != local
    json.dump(doc, open(OUT, "w", encoding="utf-8"), indent=2)
    print(json.dumps({"changed": changed, **doc}, indent=2))
    return 0 if ip else 1

if __name__ == "__main__":
    sys.exit(main())
