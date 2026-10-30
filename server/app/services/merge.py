"""Merge reports that describe the same disaster.

Two kinds of duplicates show up in social media data:

1. The same place written differently, or neighboring places for one event
   ("LA" / "Los Angeles, CA", "Altadena" / "Pasadena"). Precise clusters of the
   same type that are close together are merged.
2. A vague report of a specific event ("fires in Indonesia" alongside
   "fire in Palangka Raya"). A county/state/country cluster that contains a
   more precise cluster of the same type is folded into it.
"""

import math
from dataclasses import dataclass, field

from app.models import DisasterType, LocationPrecision
from app.services.geocode import GeoResult

# Starting radius reflects how vague the location is
BASE_RADIUS_KM = {
    LocationPrecision.address: 0.3,
    LocationPrecision.neighborhood: 1.0,
    LocationPrecision.city: 3.0,
    LocationPrecision.county: 15.0,
    LocationPrecision.state: 80.0,
    LocationPrecision.country: 250.0,
}

# Finest first
PRECISION_RANK = {p: i for i, p in enumerate(BASE_RADIUS_KM)}
COARSE = {LocationPrecision.county, LocationPrecision.state, LocationPrecision.country}

# Precise clusters closer than this multiple of their starting radius merge
NEARBY_FACTOR = 3


@dataclass
class Cluster:
    type: DisasterType
    location: str
    precision: LocationPrecision
    geo: GeoResult
    posts: list[dict]
    places: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.places:
            self.places = [self.location]

    def absorb(self, other: "Cluster") -> None:
        self.posts.extend(other.posts)
        self.places.extend(p for p in other.places if p not in self.places)


def merge_clusters(clusters: list[Cluster]) -> list[Cluster]:
    by_type: dict[DisasterType, list[Cluster]] = {}
    for c in clusters:
        by_type.setdefault(c.type, []).append(c)

    merged: list[Cluster] = []
    for group in by_type.values():
        precise = _merge_nearby([c for c in group if c.precision not in COARSE])
        coarse = sorted(
            (c for c in group if c.precision in COARSE), key=lambda c: PRECISION_RANK[c.precision]
        )
        # County first, then state, then country, so e.g. a state report can
        # fold into a city that already absorbed a county report
        final = precise
        for c in coarse:
            inside = [t for t in final if _contains(c, t)]
            if inside:
                target = max(inside, key=lambda t: (len(t.posts), -_distance_km(c.geo, t.geo)))
                target.absorb(c)
            else:
                final.append(c)
        merged.extend(final)
    return merged


def _merge_nearby(clusters: list[Cluster]) -> list[Cluster]:
    # Most specific (then best-supported) first, so it becomes the primary location
    clusters = sorted(clusters, key=lambda c: (PRECISION_RANK[c.precision], -len(c.posts)))
    result: list[Cluster] = []
    for c in clusters:
        for r in result:
            limit = NEARBY_FACTOR * max(BASE_RADIUS_KM[c.precision], BASE_RADIUS_KM[r.precision])
            if _distance_km(c.geo, r.geo) <= limit:
                r.absorb(c)
                break
        else:
            result.append(c)
    return result


def _contains(coarse: Cluster, fine: Cluster) -> bool:
    if PRECISION_RANK[fine.precision] >= PRECISION_RANK[coarse.precision]:
        return False
    a, b = coarse.geo, fine.geo
    if not a.country_code or a.country_code != b.country_code:
        return False
    if coarse.precision == LocationPrecision.country:
        return True
    # Admin names are the most reliable check when both sides have them
    if coarse.precision == LocationPrecision.county and a.county and b.county:
        return a.county == b.county
    if a.state and b.state:
        return a.state == b.state
    south, north, west, east = a.bbox
    return south <= b.lat <= north and west <= b.lng <= east


def _distance_km(a: GeoResult, b: GeoResult) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a.lat, a.lng, b.lat, b.lng))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))
