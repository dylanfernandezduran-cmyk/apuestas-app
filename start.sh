#!/usr/bin/env bash
# Inicia (o reinicia) el servidor en segundo plano. Uso: ./start.sh [puerto]   | ./start.sh stop
cd "$(dirname "$0")"
PORT="${1:-8765}"
[ "$1" = "stop" ] && { pkill -f "uvicorn server.main:app" && echo "detenido"; exit 0; }
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
pkill -f "uvicorn server.main:app" 2>/dev/null; sleep 1
nohup .venv/bin/uvicorn server.main:app --host 0.0.0.0 --port "$PORT" > server.log 2>&1 &
echo $! > server.pid
sleep 2
echo "Apuestas app en http://localhost:$PORT  (log: server.log, pid $(cat server.pid))"
