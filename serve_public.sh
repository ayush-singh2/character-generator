#!/usr/bin/env bash
#
# Serve the Character Generator from THIS laptop at a public URL.
#
#   * Streamlit runs locally (your OpenRouter key, the Flux pipeline and every
#     generated file stay on this machine).
#   * Cloudflare Tunnel exposes http://localhost:$PORT at a public https URL
#     that anyone can open — no Cloudflare account required (quick tunnel).
#
# Usage:   ./serve_public.sh
# Stop:    Ctrl-C  (tears down both Streamlit and the tunnel)
#
# NOTE: the app is fully open — anyone with the link can generate images and
# spend your OpenRouter credits (~$0.07/image). Only share the URL with people
# you trust, and Ctrl-C when you're done to take it offline.

set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8501}"
APP="${APP:-client_app.py}"

# Prefer the project venv's streamlit, fall back to whatever is on PATH.
if [[ -x "venv/bin/streamlit" ]]; then
  STREAMLIT="venv/bin/streamlit"
else
  STREAMLIT="streamlit"
fi

# Free the port first: a leftover Streamlit from a previous run would otherwise
# make this one fail with "Port $PORT is not available" while the tunnel points
# at the stale process.
if lsof -ti "tcp:$PORT" >/dev/null 2>&1; then
  echo "▶ Port $PORT busy — stopping the process holding it…"
  lsof -ti "tcp:$PORT" | xargs -r kill 2>/dev/null || true
  sleep 1
  lsof -ti "tcp:$PORT" | xargs -r kill -9 2>/dev/null || true
fi

cleanup() {
  echo
  echo "Shutting down…"
  [[ -n "${TUNNEL_PID:-}" ]] && kill "$TUNNEL_PID" 2>/dev/null || true
  [[ -n "${ST_PID:-}"     ]] && kill "$ST_PID"     2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "▶ Starting Streamlit on http://localhost:$PORT …"
"$STREAMLIT" run "$APP" \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --browser.gatherUsageStats false &
ST_PID=$!

# Wait for Streamlit to accept connections before opening the tunnel.
echo "▶ Waiting for Streamlit to come up…"
for _ in $(seq 1 30); do
  if curl -sf "http://localhost:$PORT/_stcore/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "▶ Opening public Cloudflare tunnel…"
echo "  (look for the https://<random>.trycloudflare.com URL below — that's your public link)"
echo

# Run the quick tunnel. --protocol http2 avoids QUIC/UDP 7844, which some
# networks block; drop it if your network allows QUIC and you want lower latency.
cloudflared tunnel --protocol http2 --url "http://localhost:$PORT" &
TUNNEL_PID=$!

wait "$TUNNEL_PID"
