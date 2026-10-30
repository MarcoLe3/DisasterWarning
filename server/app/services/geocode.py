"""Turn place names into coordinates with OpenStreetMap Nominatim.

Nominatim's usage policy allows at most 1 request/second and requires an
identifying User-Agent, so lookups are serialized and cached in memory.
"""

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx
from opentelemetry import metrics

logger = logging.getLogger(__name__)
meter = metrics.get_meter(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "DisasterWarning/0.1 (local development)"

geocode_lookups = meter.create_counter(
    "geocode.lookups", description="Geocoding lookups by result", unit="{lookup}"
)


@dataclass(frozen=True)
class GeoResult:
    lat: float
    lng: float
    bbox: tuple[float, float, float, float]  # south, north, west, east
    country_code: str | None
    state: str | None
    county: str | None


_cache: dict[str, GeoResult | None] = {}
_lock = asyncio.Lock()
_last_request = 0.0


async def geocode(place: str) -> GeoResult | None:
    key = place.strip().lower()
    if key in _cache:
        geocode_lookups.add(1, {"result": "cache_hit"})
        return _cache[key]

    global _last_request
    async with _lock:
        if key in _cache:  # filled while we waited for the lock
            geocode_lookups.add(1, {"result": "cache_hit"})
            return _cache[key]
        wait = 1.0 - (time.monotonic() - _last_request)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            async with httpx.AsyncClient(timeout=10, headers={"User-Agent": USER_AGENT}) as client:
                res = await client.get(
                    NOMINATIM_URL,
                    params={"q": place, "format": "json", "limit": 1, "addressdetails": 1},
                )
                res.raise_for_status()
                hits = res.json()
        except httpx.HTTPError:
            logger.exception("Geocoding failed for %r", place)
            geocode_lookups.add(1, {"result": "error"})
            return None  # not cached, so it's retried next run
        finally:
            _last_request = time.monotonic()

        result = _parse(hits[0]) if hits else None
        _cache[key] = result
        geocode_lookups.add(1, {"result": "found" if result else "not_found"})
        return result


def _parse(hit: dict) -> GeoResult:
    address = hit.get("address") or {}
    south, north, west, east = (float(v) for v in hit["boundingbox"])
    return GeoResult(
        lat=float(hit["lat"]),
        lng=float(hit["lon"]),
        bbox=(south, north, west, east),
        country_code=address.get("country_code"),
        state=address.get("state"),
        county=address.get("county"),
    )
