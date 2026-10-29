from app.models import DisasterType as T
from app.models import LocationPrecision as P
from app.services.geocode import GeoResult
from app.services.merge import Cluster, merge_clusters

# Real Nominatim results (rounded) so the tests don't need the network
THAILAND = GeoResult(14.9, 100.8, (5.61, 20.46, 97.34, 105.64), "th", None, None)
PHUKET = GeoResult(7.88, 98.39, (7.26, 8.20, 98.06, 98.49), "th", None, None)
PATONG = GeoResult(7.90, 98.31, (7.87, 7.93, 98.26, 98.32), "th", None, "อำเภอกะทู้")
BANGKOK = GeoResult(13.75, 100.49, (13.49, 13.96, 100.33, 100.94), "th", None, None)
INDONESIA = GeoResult(-2.48, 117.9, (-11.21, 6.27, 94.77, 141.02), "id", None, None)
PALANGKA_RAYA = GeoResult(-2.21, 113.92, (-2.40, -1.58, 113.48, 114.11), "id", "Kalimantan Tengah", None)
USA = GeoResult(39.78, -100.45, (-14.76, 71.59, -180.0, 180.0), "us", None, None)
TEXAS = GeoResult(31.26, -98.55, (25.84, 36.50, -106.65, -93.51), "us", "Texas", None)
HARRIS = GeoResult(29.86, -95.39, (29.50, 30.17, -95.96, -94.91), "us", "Texas", "Harris County")
HOUSTON = GeoResult(29.76, -95.37, (29.55, 30.11, -95.91, -95.01), "us", "Texas", "Harris County")
SHREVEPORT = GeoResult(32.51, -93.75, (32.37, 32.59, -93.93, -93.67), "us", "Louisiana", "Caddo Parish")
ALTADENA = GeoResult(34.19, -118.13, (34.17, 34.22, -118.17, -118.09), "us", "California", "Los Angeles County")
PASADENA = GeoResult(34.15, -118.14, (34.12, 34.25, -118.20, -118.07), "us", "California", "Los Angeles County")
LOS_ANGELES = GeoResult(34.05, -118.24, (33.70, 34.34, -118.67, -118.16), "us", "California", "Los Angeles County")


def cluster(t, name, precision, geo, n_posts=1):
    return Cluster(t, name, precision, geo, [{"id": f"{name}-{i}"} for i in range(n_posts)])


def by_location(clusters):
    return {c.location: c for c in clusters}


def test_country_report_folds_into_city_in_same_country():
    result = merge_clusters([
        cluster(T.fire, "Indonesia", P.country, INDONESIA),
        cluster(T.fire, "Palangka Raya", P.city, PALANGKA_RAYA),
    ])
    assert len(result) == 1
    assert result[0].location == "Palangka Raya"
    assert result[0].places == ["Palangka Raya", "Indonesia"]
    assert len(result[0].posts) == 2


def test_country_report_goes_to_best_supported_city():
    result = by_location(merge_clusters([
        cluster(T.flood, "Thailand", P.country, THAILAND),
        cluster(T.flood, "Bangkok", P.city, BANGKOK, n_posts=1),
        cluster(T.flood, "Patong", P.neighborhood, PATONG, n_posts=3),
    ]))
    assert set(result) == {"Bangkok", "Patong"}
    assert "Thailand" in result["Patong"].places
    assert len(result["Bangkok"].posts) == 1


def test_province_without_state_field_uses_bounding_box():
    result = merge_clusters([
        cluster(T.flood, "Phuket", P.state, PHUKET),
        cluster(T.flood, "Patong", P.neighborhood, PATONG),
    ])
    assert [c.location for c in result] == ["Patong"]


def test_coarse_reports_chain_county_then_state_then_country():
    result = merge_clusters([
        cluster(T.flood, "USA", P.country, USA),
        cluster(T.flood, "Texas", P.state, TEXAS),
        cluster(T.flood, "Harris County", P.county, HARRIS),
        cluster(T.flood, "Houston", P.city, HOUSTON),
    ])
    assert len(result) == 1
    assert result[0].location == "Houston"
    assert result[0].places == ["Houston", "Harris County", "Texas", "USA"]


def test_coarse_without_finer_match_stays_separate():
    result = by_location(merge_clusters([
        cluster(T.fire, "Texas", P.state, TEXAS),
        cluster(T.fire, "Palangka Raya", P.city, PALANGKA_RAYA),
    ]))
    assert set(result) == {"Texas", "Palangka Raya"}


def test_us_bounding_box_does_not_swallow_other_countries():
    # The USA's bbox spans every longitude; country code must still match
    result = merge_clusters([
        cluster(T.fire, "USA", P.country, USA),
        cluster(T.fire, "Palangka Raya", P.city, PALANGKA_RAYA),
    ])
    assert len(result) == 2


def test_state_name_beats_bounding_box_overlap():
    # Shreveport, LA sits inside Texas's bounding box but is in Louisiana
    result = merge_clusters([
        cluster(T.flood, "Texas", P.state, TEXAS),
        cluster(T.flood, "Shreveport", P.city, SHREVEPORT),
    ])
    assert len(result) == 2


def test_different_types_never_merge():
    result = merge_clusters([
        cluster(T.fire, "Houston", P.city, HOUSTON),
        cluster(T.flood, "Texas", P.state, TEXAS),
    ])
    assert len(result) == 2


def test_nearby_precise_reports_merge_into_most_specific():
    result = merge_clusters([
        cluster(T.fire, "Pasadena", P.city, PASADENA, n_posts=2),
        cluster(T.fire, "Altadena", P.neighborhood, ALTADENA),
    ])
    assert len(result) == 1
    assert result[0].location == "Altadena"
    assert result[0].places == ["Altadena", "Pasadena"]
    assert len(result[0].posts) == 3


def test_same_city_written_differently_merges():
    result = merge_clusters([
        cluster(T.fire, "Los Angeles, CA", P.city, LOS_ANGELES),
        cluster(T.fire, "LA", P.city, LOS_ANGELES),
    ])
    assert len(result) == 1


def test_distant_precise_reports_stay_separate():
    # LA downtown to Altadena is ~16 km, beyond 3x the 3 km city radius
    result = merge_clusters([
        cluster(T.fire, "Los Angeles", P.city, LOS_ANGELES),
        cluster(T.fire, "Altadena", P.neighborhood, ALTADENA),
    ])
    assert len(result) == 2
