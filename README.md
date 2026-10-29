# DisasterWarning

Scrapes TikTok (via Apify) for disaster posts, uses Claude to keep only real current reports and extract type + location, geocodes them, and shows them on a map with an estimated spread over time.

| Folder | Stack |
| --- | --- |
| `client/` | React + Vite + Leaflet |
| `server/` | FastAPI |

## Running locally

```bash
docker compose up -d                       # observability stack (optional)
cd server && source .venv/bin/activate && fastapi dev app/main.py
cd client && npm run dev                   # http://localhost:5173
```

Put `APIFY_TOKEN` and `ANTHROPIC_API_KEY` in `server/.env`. Without an Apify token the server serves mock data.

## Observability (OpenTelemetry)

Both apps export over OTLP to the `grafana/otel-lgtm` container. Open Grafana at http://localhost:3000 (admin / admin):

- **Traces → Tempo**: browser page loads, clicks and fetches → FastAPI requests → Apify, Claude and geocoding calls, all in one trace
- **Metrics → Prometheus**: HTTP server latency/sizes, Apify run count/duration, Claude requests/latency/tokens, geocode lookups, posts scraped/classified, cache hit rate, active disasters by type, plus CPU/memory/GC system metrics
- **Logs → Loki**: server logs with trace/span IDs for jumping between logs and traces

Disable with `OTEL_SDK_DISABLED=true` (server) or `VITE_OTEL_DISABLED=true` (client).
