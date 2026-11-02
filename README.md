---
title: Apuestas App
emoji: 🎯
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# 🎯 Picks Terminal — app de picks deportivos (MVP)

Eliges deporte → juego → ves estadísticas, tendencias, cuotas (con probabilidad sin vig) y **Mejores picks**.
UI 100% en español, tema oscuro estilo terminal, responsive. Horas en CDMX (UTC-6).

## Iniciar
```
cd /workspace/apuestas-app
./start.sh          # puerto 8765 (o ./start.sh 9000)
./start.sh stop     # detener
```
Abre http://localhost:8765 · logs en `server.log` · pid en `server.pid`.
(El script crea `.venv` e instala `requirements.txt` la primera vez; corre en segundo plano con nohup. No se reinicia solo tras un reboot de la máquina.)

## Deportes
MLB · NFL · NBA · NHL · Tenis (ATP/WTA) · Fútbol (Liga MX, Premier, LaLiga, Serie A, Bundesliga, Champions).

## Fuentes (gratis, sin llaves)
- ESPN `site.api.espn.com`: scoreboard, summary (cuotas DraftKings, lesiones, líderes, H2H), calendarios de equipos, rankings de tenis.
- MLB StatsAPI `statsapi.mlb.com`: pitchers probables y sus stats.
Caché en memoria con TTL (scoreboard 1–5 min, summary ~2 min, calendarios/ratings 1 h) y reintentos; si la fuente falla se sirve el último dato.

## API
`/api/sports` · `/api/games?league=nba&days=3` · `/api/game/{league}/{eventId}` · `/api/picks?scope=24h|hoy|manana|72h` · `/api/health`

## Modelo (simple y transparente — estimación, no garantía)
- Deportes de margen: ratings SRS (40 iteraciones) con encogimiento por muestra, ventaja de local estimada con prior, distribución normal para ML/spread/total.
- Fútbol: Poisson con fuerza de ataque/defensa suavizada → 1X2, hándicap, totales.
- Tenis: logística sobre puntos de ranking (sin cuotas disponibles).
- Prob. final = mezcla modelo/mercado (sin vig), peso según tamaño de muestra; el modelo se limita a ±20 pp del mercado.
- Edge = final − sin vig; EV = final×decimal − 1; línea justa; precio máximo = EV +2%.
- PICK: edge ≥3 pp y EV ≥0 (confianza Baja baja a LEAN). LEAN: edge ≥1 pp. PASS: sin edge (siempre se muestra la inclinación). SIN LÍNEA: no hay precio de mercado.
- No considera lesiones, descanso ni clima en la probabilidad (se muestran como información).

## Política de datos
Solo datos reales. Si no existe: **"Sin dato"**. Lo confirmado (OUT/IR/suspensión) se separa de lo por confirmar (día a día, dudoso, pitcher probable).

## Aviso
Estimaciones de un modelo simple con fines informativos. No hay promesa de rentabilidad. Apuesta con responsabilidad.

## Despliegue en Render (plan gratuito)
- Build: `pip install -r requirements.txt`
- Start: `uvicorn server.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/health` (ver `render.yaml`; o "New → Blueprint" apuntando a este repo).
- No requiere variables de entorno ni llaves. El plan gratuito se duerme tras ~15 min sin tráfico (el primer acceso tarda ~1 min en despertar y recalcular ratings).
