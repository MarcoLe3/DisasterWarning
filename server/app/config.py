import os

from dotenv import load_dotenv

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
APIFY_SEARCH_QUERIES = [
    q.strip()
    for q in os.getenv(
        "APIFY_SEARCH_QUERIES", "wildfire,house fire,flood,earthquake,hurricane,tornado"
    ).split(",")
    if q.strip()
]
APIFY_RESULTS_PER_QUERY = int(os.getenv("APIFY_RESULTS_PER_QUERY", "20"))
APIFY_MAX_POST_AGE_DAYS = int(os.getenv("APIFY_MAX_POST_AGE_DAYS", "3"))
APIFY_CACHE_TTL_SECONDS = int(os.getenv("APIFY_CACHE_TTL_SECONDS", "900"))
CLIENT_ORIGIN = os.getenv("CLIENT_ORIGIN", "http://localhost:5173")

# The Anthropic SDK reads ANTHROPIC_API_KEY from the environment itself
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "disasterwarning-server")
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
OTEL_SDK_DISABLED = os.getenv("OTEL_SDK_DISABLED", "false").lower() == "true"
