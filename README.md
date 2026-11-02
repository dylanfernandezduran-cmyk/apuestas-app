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
- ESPN `/injuries`, `/summary` (alineaciones, box score, jugadas), `/teams/{id}/depthcharts` (NFL).
- Open-Meteo (geocodificación + pronóstico por hora, sin llave) para el clima.
Caché en memoria con TTL (scoreboard 1–5 min, summary ~2 min, calendarios/ratings 1 h) y reintentos; si la fuente falla se sirve el último dato.

## En vivo, lesiones, clima y alineaciones (v6)
Todo con datos reales (ESPN y Open-Meteo); si algo no existe se muestra «Sin dato» — nunca se inventa.

| | NBA | NFL | NHL | MLB | Fútbol | Tenis |
|---|---|---|---|---|---|---|
| **En vivo** (marcador, reloj, periodo) | ✅ | ✅ posesión/down/zona roja | ✅ | ✅ outs/cuenta/corredores/bateador* | ✅ minuto, stats, jugadas | ✅ sets/juegos |
| **Calificación provisional** del pick («ganando/perdiendo ahora») | ✅ | ✅ | ✅ | ✅ | ✅ (1X2 con empate) | — (sólo al terminar) |
| **Lesiones** por equipo (estado, lesión, fecha, regreso estimado) | ✅ | ✅ | ✅ | ✅* | ⚠️ ESPN no publica | retiros/WO en la tarjeta |
| **Clima** en la hora del juego (Open-Meteo) | — | ✅ (techados: «Techado») | — | ✅* | ✅ | — |
| **Alineaciones** | titulares (proyectados→confirmados) | depth chart con bajas | portero | alineación + abridor probable* | XI + formación cuando ESPN la publica | — |
| **Descanso / back-to-back** | ✅ | — | ✅ | — | — | — |

\* MLB está en receso invernal: el código está probado con datos reales de temporada pero no hay juegos para verlo hoy.

- **Auto-actualización:** la lista y el detalle se refrescan cada ~25 s sólo si hay un juego en vivo (o por empezar) y la pestaña está visible; cada bloque muestra «Actualizado hh:mm:ss CDMX».
- **Provisional ≠ final:** el chip «ganando ahora» usa sólo el marcador actual; en totales se marca 🔒 cuando ya no puede cambiar. La calificación oficial sigue siendo la del Récord (al terminar).
- **«Regresa de lesión»:** ESPN no lo publica. Lo derivamos de nuestro propio seguimiento en SQLite (tablas `inj_cur`/`inj_events`): un jugador «regresa» si salió del reporte o mejoró de estado en los últimos 10 días *desde que el servidor empezó a seguir esa liga* (se muestra la fecha de inicio). La primera lectura sólo fija la línea base (no inventa eventos). Es una señal, no una confirmación de que jugará.
- **Alineaciones:** «✅ confirmada» = publicada por ESPN; «❓ proyectada» = titulares del último juego terminado del equipo (rotulado, puede cambiar). Los cambios («X entra por Y») se calculan contra la foto anterior guardada (`lineup_snap`) y sólo se reportan cuando la alineación es confirmada. Un hilo en segundo plano guarda fotos cada 10 min para juegos cercanos.
- **Clima:** coordenadas por geocodificación de ciudad/estado del estadio (caché en SQLite), pronóstico en la hora del partido (CDMX), temp., viento (km/h y dirección de donde sopla), prob. de lluvia, humedad. Las notas («viento fuerte», «lluvia probable»…) son contexto con umbrales generales; **no modifican** las probabilidades del modelo.
- **Limitaciones conocidas:** ESPN no entrega lesiones/suspensiones de fútbol ni inactivos oficiales de NFL en sus endpoints públicos; la NHL no publica portero probable antes del juego (se muestra el del último juego, rotulado «no confirmado»); las jugadas en vivo vienen en inglés de ESPN; los stats de equipo antes del juego son promedios de temporada, así que sólo se muestran durante/después.

## Marca, logo y app instalable (PWA)
- **3 opciones** de nombre/logo en `static/brand/{ventaja,pizarra,vigia}/glyph.svg` (vista previa: `screens/logos_options.png` o `/static/brand/options.html`). Por defecto: **Ventaja**.
- **4 opciones «el ojo que todo lo ve»** (minimalistas, ojo + deporte): `avizor` (iris = pelota), `atalaya` (ojo en torre/cancha), `zahori` (iris = cancha vista desde arriba), `lince` (pupila = diana). Hoja: `screens/logos_ojo_options.png`; maquetas iPhone: `screens/logo_ojo_<nombre>.png` (`python scripts/make_brand_sheet.py avizor atalaya zahori lince`). - **Nombre elegido: «No Risk No Money» (NRNM)** — opción `nrnm` (ojo en triángulo, pupila = pelota, base = línea de cancha), `nrnm_oro` (acento dorado) y variantes `tri_bola`, `tri_rayos`, `tri_avizor`, `tri_badge` (generadas con `scripts/gen_triangle_glyphs.py`). Hoja: `screens/logos_triangulo_options.png`; maquetas: `screens/logo_nrnm.png`, `screens/logo_nrnm_oro.png`. Aún no activada: `python scripts/make_icons.py nrnm`. El campo opcional `short` de brand.json (NRNM) se usa en el encabezado, el manifest y el título en iOS.
- **Paleta NRNM** (`palette` en brand.json → variables CSS en `:root`; otras marcas no cambian): rosa `#FF1179` = marca/CTA (`--acc`), teal `#06AAC4` = ganado/positivo (`--grn`), azul `#3C85F7` = en vivo/info (`--live`, `--blu`), naranja-rojo `#FF6B4A` = pérdida (`--red`), ámbar `#fbbf24` = aviso. Colorways: `nrnm` (rosa neón), `nrnm_degradado`, `nrnm_azul` (`scripts/gen_nrnm_colorways.py`). Hoja: `screens/nrnm_paleta.png` (`scripts/make_palette_sheet.py`). Probar sin activar: `BRAND=nrnm uvicorn server.main:app --port 8766`.
- **NRNM v2** (estilo de la referencia: triángulo monolínea + ojo con iris/brillo + barra, sin porterías ni balones): `nrnm_v2_1..5` (todo rosa · iris teal · iris azul · rosa metálico + teal · degradado rosa→azul + teal), con `icon_bg` carbón `#171b21`. Hoja `screens/nrnm_v2_options.png`, mocks `screens/logo_nrnm_v2_<n>.png`; se generan con `scripts/gen_nrnm_v2.py` y `scripts/make_v2_sheet.py`.
- **Marca activa: `nrnm_final_blanco_americano`** (todo blanco sobre negro `#000`, balón americano; antes `nrnm_final` rosa) — anterior: **`nrnm_final`** — «No Risk No Money» (NRNM): triángulo completo + ojo, todo rosa `#FF1179`, sin barra; íconos con fondo carbón `#171b21`. Variantes con la pupila como balón (no activas): `nrnm_final_futbol`, `_basket`, `_beisbol`, `_americano` (generadas con `scripts/gen_nrnm_final.py`; hoja `screens/nrnm_final_balones.png`). Para cambiar: `python scripts/make_icons.py <opcion>`.
- Para ver los íconos de una opción sin activarla: `python scripts/make_icons.py avizor --preview`.
- **Cambiar de marca** (una línea): edita `"active"` en `static/brand/brand.json` (o ejecuta con la variable de entorno `BRAND=pizarra`), y regenera íconos con `python scripts/make_icons.py pizarra` (usa Playwright/Chrome; escribe `static/brand/icons/*`). El nombre, eslogan, logo del encabezado, splash, `manifest.webmanifest` y metas de iOS se rellenan solos desde esa config.
- **Splash:** animación corta del logo, una vez por sesión, se salta con un toque (`/?splash=1` lo fuerza; `?splash=1&hold=1` lo mantiene para capturas).
- **Instalar en el teléfono:**
  - *iPhone (Safari):* abre la URL de tu PC en la LAN (p. ej. `http://192.168.x.x:8765`) → Compartir → «Añadir a pantalla de inicio». Con `http://` funciona como app independiente (icono, pantalla completa, color de barra) pero **sin modo sin conexión**: el service worker sólo se registra en HTTPS (o `localhost`).
  - *Android (Chrome):* «Instalar app» requiere HTTPS o `localhost`; por `http` en la LAN queda como acceso directo.
  - *Con HTTPS* (p. ej. un túnel como Cloudflare Tunnel/ngrok, o el despliegue en Render): instalación completa + shell offline (`static/sw.js`: cachea la interfaz; los datos van siempre a la red primero y nunca se cachea `/api/live`).

## Mercado: casas, % apuestas, RLM y movimientos
En cada juego (antes de empezar) la ficha muestra:
- **Comparador de casas** (ML, spread/hándicap, total): Pinnacle (sharp) + DraftKings, FanDuel, BetMGM, Caesars, BetRivers, bet365, Fanatics, Unibet (según el juego), consenso y apertura. Mejor precio y mejor línea resaltados; probabilidad de consenso sin vig.
- **% tickets / % dinero** por lado, con fuente y hora (CDMX). Sin fuente para el juego ⇒ "Sin dato" (nunca se estima).
- **RLM y dinero inteligente** (indicadores, no garantías): lado público (≥55% tickets) contra el que se mueve la línea/precio entre la apertura y ahora; y % dinero − % tickets ≥ 10 pp.
- **Movimientos**: apertura vs actual por mercado + historial propio por casa con gráfica (SVG). El servidor guarda en SQLite un snapshot cada `SNAP_MIN` min (sólo cuando algo cambia) de los juegos de las próximas 72 h.
- Las señales aparecen junto a cada pick (etiquetas a favor / en contra / mixto) **sin modificar** la probabilidad del modelo.

| Fuente | Qué aporta | Cobertura |
|---|---|---|
| Action Network (API pública sin llave) | 8 casas de EE. UU., consenso, apertura, % tickets y % dinero | NBA, NFL, NHL, MLB, NCAAF, NCAAB, fútbol (EPL, LaLiga, Serie A, Ligue 1, Bundesliga, Champions, Europa, MLS). No Liga MX ni tenis |
| Pinnacle (API de invitado, llave pública del sitio) | línea sharp, sin splits | Todos, incl. Liga MX y tenis (sólo juegos cercanos) |
| ESPN | DraftKings (respaldo) | según el juego |

Opción con llave gratuita (no incluida): The Odds API (más casas, sin splits). Estas APIs no son oficiales y pueden cambiar o bloquearse: el app degrada a "Sin dato".

Variables de entorno opcionales: `SNAP_MIN` (default 10), `PINNACLE=0` (desactiva Pinnacle), `PINNACLE_GUEST_KEY`, `GRADE_MIN` (min entre calificaciones, default 10), `APUESTAS_DB` (ruta del SQLite; default `data/history.db`).

## Probabilidades por resultado
Cada juego (pre-juego) tiene una sección **Probabilidades** con todos los resultados de ganador/1X2, doble oportunidad (fútbol), hándicap/spread/run line/puck line y over/under, siempre con el nombre del equipo/jugador (p. ej. «Lakers (local)»): prob. del modelo, prob. sin vig del consenso y de Pinnacle, prob. final (mezcla), línea justa, mejor precio y casa, y edge. Las tarjetas de lista y Top picks muestran el mejor resultado por mercado (`/api/league_brief?league=nba`). Sin dato del modelo (p. ej. hándicap/totales de tenis, líneas de cuarto): sólo mercado y «Modelo: Sin dato».

**Tenis:** ganador (sin empate, 1X2 ni doble oportunidad) + **Hándicap de juegos** (p. ej. «Sinner -3.5 juegos»), **Total de juegos** (p. ej. «Over 22.5 juegos») y, cuando Pinnacle los publica, **Hándicap de sets** y **Total de sets**. En Pinnacle el matchup principal de tenis trae los mercados de SETS (±1.5 / 2.5); los de JUEGOS viven en un matchup relacionado (units «Games»), que ahora se lee aparte. Convención interna: `spread`/`total` = juegos, `sspread`/`stotal` = sets. Sólo el ganador tiene modelo; el resto es mercado.

## Récord: ¿se ganó el pick? (`📒 Récord`)
- **Registro:** cada vez que se genera el análisis de un juego *pre-juego* (al abrirlo, en listas/Top picks, o por el snapshot automático de las próximas 72 h) se guardan en SQLite (tabla `picks`) el **pick principal** y las **sugerencias**: deporte, liga, juego, hora, equipos, mercado, selección, línea, cuota/casa, prob. del modelo, tipo y `created_at`. Una fila por juego+mercado+selección; se conserva **la primera línea/cuota** (nunca se sobrescribe), un solo principal por juego y un solo lado por mercado. Nada se registra una vez iniciado el juego.
- **Calificación:** `grade_loop` cada `GRADE_MIN` min (default 10) y `POST /api/grade` (botón «Calificar ahora»). Sólo con el **marcador final confirmado** de ESPN (summary para equipos, scoreboard para tenis); si no hay final sigue ⏳ Pendiente (nunca se inventa). Estados: ✅ Ganado · ❌ Perdido · ➖ Push · medio ganado/perdido (líneas de cuarto, p. ej. -0.75, 2.25) · ⚪ Anulado (cancelado/WO/retiro; pospuesto >7 días).
- **Reglas:** tiempo extra cuenta en NBA/NFL/NHL/MLB; NHL: el gol de la tanda de penales no cuenta para el total; fútbol 1X2/hándicap/total a 90' (+descuento; con prórroga se usa la suma de los dos tiempos o queda pendiente); empate en ML de 2 vías (NFL) = push; tenis: hándicap/total de **juegos** y de **sets** calculados desde el marcador por sets.
- **Unidades:** apuesta plana de 1u a la cuota registrada (picks sin cuota no entran en unidades/ROI).
- **Historial desde que se empezó a registrar:** no hay backfill — no existen las cuotas/probabilidades pre-juego de partidos pasados y regenerarlos usaría el resultado. Filas con `source` ≠ `live` (p. ej. `scripts/demo_grade_finals.py`) se avisan en la UI.
- **Límites:** el scoreboard de tenis de ESPN sólo lista torneos actuales (un partido que ya no aparece queda pendiente con nota); MLB está en receso; marcadores atípicos (súper tie-break) quedan pendientes.
- **Pruebas:** `pip install -r requirements-dev.txt && pytest` (liquidación, fixtures reales de ESPN, registro/dedupe, tenis). `scripts/demo_grade_finals.py` califica en vivo picks SINTÉTICOS sobre finales reales de ayer (BD aparte) y los compara con un cálculo independiente; `scripts/check_tennis_live.py` revisa lados/unidades de tenis en vivo.

## API
`/api/sports` · `/api/games?league=nba&days=3` · `/api/game/{league}/{eventId}` (incluye `market`) · `/api/history/{league}/{eventId}` · `/api/picks?scope=24h|hoy|manana|72h` · `POST /api/snapshot` · `/api/record?sport=&type=main|suggestion&basis=modelo|mercado&days=&limit=` (resumen + últimos calificados) · `/api/record/game/{league}/{eventId}` · `POST /api/grade` · `/api/live` · `/api/league_wx?league=` · `/api/home` · `/api/brand` · `/manifest.webmanifest` · `/api/health`

## Windows
`py -m venv .venv` · `.venv\Scripts\pip install -r requirements.txt` (incluye `tzdata`, necesario en Windows) · `.venv\Scripts\python -m uvicorn server.main:app --host 0.0.0.0 --port 8765`

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
