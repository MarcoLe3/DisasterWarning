"""Apify integration: scrape TikTok for disaster posts and group them into disasters.

Pipeline: Apify TikTok scraper -> Claude classification -> geocoding -> grouping.
If APIFY_TOKEN isn't set, falls back to mock data so the client still has
something to render.
"""

import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import httpx
from opentelemetry import metrics, trace

from app.config import (
    APIFY_CACHE_TTL_SECONDS,
    APIFY_MAX_POST_AGE_DAYS,
    APIFY_RESULTS_PER_QUERY,
    APIFY_SEARCH_QUERIES,
    APIFY_TOKEN,
)
from app.models import Disaster, DisasterType, LocationPrecision, SourcePost, SpreadPoint
from app.services.classify import classify_posts
from app.services.geocode import geocode

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

ACTOR_ID = "clockworks~tiktok-scraper"
RUN_SYNC_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
SPREAD_BUCKET = timedelta(hours=6)

# Starting radius reflects how vague the location is
BASE_RADIUS_KM = {
    LocationPrecision.address: 0.3,
    LocationPrecision.neighborhood: 1.0,
    LocationPrecision.city: 3.0,
    LocationPrecision.county: 15.0,
    LocationPrecision.state: 80.0,
    LocationPrecision.country: 250.0,
}

apify_runs = meter.create_counter(
    "apify.runs", description="Apify actor runs", unit="{run}"
)
apify_run_duration = meter.create_histogram(
    "apify.run.duration", description="Apify actor run duration", unit="s"
)
posts_scraped = meter.create_counter(
    "disaster.posts.scraped", description="Posts returned by Apify", unit="{post}"
)
posts_classified = meter.create_counter(
    "disaster.posts.classified",
    description="Posts by classification outcome",
    unit="{post}",
)
cache_lookups = meter.create_counter(
    "disaster.cache.lookups", description="Disaster cache hits/misses", unit="{lookup}"
)

_cache: list[Disaster] = []
_cache_expires_at = 0.0


def _observe_active(_options):
    counts: dict[str, int] = defaultdict(int)
    for d in _cache:
        counts[d.type.value] += 1
    return [metrics.Observation(n, {"disaster.type": t}) for t, n in counts.items()]


meter.create_observable_gauge(
    "disaster.active",
    callbacks=[_observe_active],
    description="Disasters currently tracked",
    unit="{disaster}",
)


async def fetch_disasters() -> list[Disaster]:
    global _cache, _cache_expires_at
    if time.monotonic() < _cache_expires_at:
        cache_lookups.add(1, {"result": "hit"})
        return _cache
    cache_lookups.add(1, {"result": "miss"})

    if not APIFY_TOKEN:
        logger.warning("APIFY_TOKEN not set, serving mock disasters")
        _cache = _mock_disasters()
    else:
        posts = await _run_scraper()
        _cache = await _group_posts(posts)
    _cache_expires_at = time.monotonic() + APIFY_CACHE_TTL_SECONDS
    return _cache


async def _run_scraper() -> list[dict]:
    payload = {
        "searchQueries": APIFY_SEARCH_QUERIES,
        "resultsPerPage": APIFY_RESULTS_PER_QUERY,
        "searchSection": "/video",
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSlideshowImages": False,
    }
    with tracer.start_as_current_span("apify.run", attributes={"apify.actor": ACTOR_ID}) as span:
        start = time.perf_counter()
        status = "error"
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                res = await client.post(
                    RUN_SYNC_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {APIFY_TOKEN}"},
                )
                res.raise_for_status()
                items = [i for i in res.json() if "errorCode" not in i]
            status = "ok"
            span.set_attribute("apify.items", len(items))
            posts_scraped.add(len(items))
            logger.info("Apify returned %d posts", len(items))
            return items
        except httpx.HTTPError as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR)
            logger.exception("Apify run failed")
            raise
        finally:
            apify_runs.add(1, {"status": status})
            apify_run_duration.record(time.perf_counter() - start, {"status": status})


async def _group_posts(items: list[dict]) -> list[Disaster]:
    with tracer.start_as_current_span("disaster.group_posts") as span:
        unique = list({str(i.get("id")): i for i in items}.values())
        # Apify's date filters don't apply to search results, so filter here
        # (also avoids paying Claude to classify stale posts)
        cutoff = datetime.now(timezone.utc) - timedelta(days=APIFY_MAX_POST_AGE_DAYS)
        recent = [i for i in unique if _posted_at(i) >= cutoff]
        posts_classified.add(len(unique) - len(recent), {"outcome": "too_old"})
        span.set_attribute("disaster.posts.recent", len(recent))
        unique = recent
        classifications = await classify_posts(unique)

        Group = list[tuple[dict, LocationPrecision]]
        groups: dict[tuple[DisasterType, str], Group] = defaultdict(list)
        for item in unique:
            c = classifications.get(str(item.get("id")))
            if c is None:
                posts_classified.add(1, {"outcome": "unclassified"})
            elif not c.is_current_disaster_report or c.disaster_type is None:
                posts_classified.add(1, {"outcome": "not_a_report"})
            elif not c.location or c.precision is None:
                posts_classified.add(1, {"outcome": "no_location"})
            else:
                posts_classified.add(1, {"outcome": "ok", "disaster.type": c.disaster_type.value})
                groups[(c.disaster_type, c.location)].append((item, c.precision))

        disasters = []
        for (dtype, location), posts in groups.items():
            coords = await geocode(location)
            if coords is None:
                posts_classified.add(len(posts), {"outcome": "geocode_failed"})
                continue
            disasters.append(_build_disaster(dtype, location, coords, posts))

        span.set_attribute("disaster.count", len(disasters))
        return sorted(disasters, key=lambda d: d.severity, reverse=True)


def _posted_at(item: dict) -> datetime:
    raw = item.get("createTimeISO")
    if raw:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if item.get("createTime"):
        return datetime.fromtimestamp(int(item["createTime"]), timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


def _build_disaster(
    dtype: DisasterType,
    location: str,
    coords: tuple[float, float],
    posts: list[tuple[dict, LocationPrecision]],
) -> Disaster:
    # Use the most specific precision any post gave for this place
    precision = min((p for _, p in posts), key=lambda p: BASE_RADIUS_KM[p])
    sources = sorted(
        (
            SourcePost(
                platform="tiktok",
                url=item.get("webVideoUrl") or "",
                caption=(item.get("text") or "")[:280],
                posted_at=item.get("createTimeISO") or datetime.now(timezone.utc),
            )
            for item, _ in posts
        ),
        key=lambda s: s.posted_at,
    )
    slug = re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-")
    return Disaster(
        id=f"{dtype.value}-{slug}",
        type=dtype,
        title=f"{dtype.value.capitalize()} reports in {location}",
        location=location,
        precision=precision,
        lat=coords[0],
        lng=coords[1],
        severity=min(5, 1 + len(sources) // 3),
        spread=_estimate_spread(sources, BASE_RADIUS_KM[precision]),
        sources=sources,
    )


def _estimate_spread(sources: list[SourcePost], base_km: float) -> list[SpreadPoint]:
    """Rough proxy: radius grows with cumulative post volume per 6h bucket.

    Social posts don't tell us real fire perimeters; swap this for an official
    feed (e.g. NASA FIRMS, NIFC perimeters) when available.
    """
    if not sources:
        return []
    start = sources[0].posted_at
    points: list[SpreadPoint] = []
    count = 0
    bucket_end = start + SPREAD_BUCKET
    for s in sources:
        while s.posted_at >= bucket_end:
            points.append(SpreadPoint(timestamp=bucket_end - SPREAD_BUCKET, radius_km=_radius(base_km, count)))
            bucket_end += SPREAD_BUCKET
        count += 1
    points.append(SpreadPoint(timestamp=bucket_end - SPREAD_BUCKET, radius_km=_radius(base_km, count)))
    return points


def _radius(base_km: float, post_count: int) -> float:
    return round(base_km * (1 + 0.2 * max(post_count - 1, 0)), 1)


def _mock_spread(start: datetime, radii: list[float]) -> list[SpreadPoint]:
    return [
        SpreadPoint(timestamp=start + timedelta(hours=i * 6), radius_km=r)
        for i, r in enumerate(radii)
    ]


def _mock_disasters() -> list[Disaster]:
    now = datetime.now(timezone.utc)
    return [
        Disaster(
            id="fire-la-1",
            type=DisasterType.fire,
            title="Brush fire spreading near hillside homes",
            location="Los Angeles, California, USA",
            precision=LocationPrecision.city,
            lat=34.1184,
            lng=-118.3004,
            severity=4,
            spread=_mock_spread(now - timedelta(hours=18), [0.5, 1.2, 2.0, 2.8]),
            sources=[
                SourcePost(
                    platform="tiktok",
                    url="https://www.tiktok.com/",
                    caption="Smoke everywhere over Griffith Park right now",
                    posted_at=now - timedelta(hours=17),
                )
            ],
        ),
        Disaster(
            id="flood-houston-1",
            type=DisasterType.flood,
            title="Flash flooding on major roads",
            location="Houston, Texas, USA",
            precision=LocationPrecision.city,
            lat=29.7604,
            lng=-95.3698,
            severity=3,
            spread=_mock_spread(now - timedelta(hours=12), [1.0, 2.5, 3.0]),
            sources=[
                SourcePost(
                    platform="tiktok",
                    url="https://www.tiktok.com/",
                    caption="Streets turned into rivers downtown",
                    posted_at=now - timedelta(hours=11),
                )
            ],
        ),
    ]
