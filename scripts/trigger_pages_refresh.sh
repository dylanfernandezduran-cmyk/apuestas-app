#!/bin/sh
# Dispara un refresh de la versión en línea (GitHub Pages) SIN usar el cron poco fiable de Actions.
# NO guardes el token en el repo ni en este archivo.
#
# Opción A — desde una terminal (el token no se imprime):
#   GITHUB_TOKEN=ghp_... ./scripts/trigger_pages_refresh.sh
#   El token necesita permiso "actions: write" en dylanfernandezduran-cmyk/apuestas-app.
#
# Opción B — cron-job.org (u otro cron externo), cada 15 min:
#   POST https://api.github.com/repos/dylanfernandezduran-cmyk/apuestas-app/dispatches
#   Headers:
#     Authorization: Bearer <PAT>
#     Accept: application/vnd.github+json
#     X-GitHub-Api-Version: 2022-11-28
#   Body: {"event_type":"refresh-pages"}
#
# Opción C — workflow_dispatch:
#   POST https://api.github.com/repos/dylanfernandezduran-cmyk/apuestas-app/actions/workflows/pages.yml/dispatches
#   Body: {"ref":"main"}
#
# El workflow nuevo está en scripts/pages.workflow.yml (hay que copiarlo a
# .github/workflows/pages.yml con un token que tenga alcance «workflow»).
# Esto no se configura aquí: el dueño tiene que crear el PAT y el cron en su cuenta.
set -eu
REPO="${GITHUB_REPOSITORY:-dylanfernandezduran-cmyk/apuestas-app}"
TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
if [ -z "$TOKEN" ]; then
  echo "Falta GITHUB_TOKEN o GH_TOKEN (no lo pegues en el repo)." >&2
  exit 1
fi
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${REPO}/dispatches" \
  -d '{"event_type":"refresh-pages"}'
echo
echo "Dispatched refresh-pages on $REPO"
