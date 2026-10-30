# Server (FastAPI)

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then add APIFY_TOKEN and ANTHROPIC_API_KEY
fastapi dev app/main.py   # http://localhost:8000, docs at /docs
```

- `app/services/apify.py` – runs the Apify TikTok scraper, drops posts older than `APIFY_MAX_POST_AGE_DAYS`, groups posts into disasters (mock data if no `APIFY_TOKEN`)
- `app/services/classify.py` – Claude decides whether each post is a real, current disaster report and extracts type + most specific location
- `app/services/geocode.py` – OpenStreetMap Nominatim geocoding (1 req/s, cached)
- `app/routers/disasters.py` – `/api/disasters` endpoints
- `app/telemetry.py` – OpenTelemetry traces, metrics and logs (OTLP → see root `docker-compose.yml`)

Scraper results are cached for `APIFY_CACHE_TTL_SECONDS` (default 15 min) since each Apify run costs credits.
