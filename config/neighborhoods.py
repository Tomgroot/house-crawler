from dataclasses import dataclass


@dataclass(frozen=True)
class NeighborhoodConfig:
    name: str
    slugs: list[str]
    distance_to_station_km: float
    lat_center: float
    lon_center: float


NEIGHBORHOODS: list[NeighborhoodConfig] = [
    NeighborhoodConfig(
        name="Binnenstad",
        slugs=["binnenstad"],
        distance_to_station_km=0.5,
        lat_center=52.0907,
        lon_center=5.1214,
    ),
    NeighborhoodConfig(
        name="Lombok",
        slugs=["lombok-west", "lombok-oost"],
        distance_to_station_km=1.2,
        lat_center=52.0886,
        lon_center=5.0999,
    ),
    NeighborhoodConfig(
        name="Wittevrouwen/Oudwijk",
        slugs=["wittevrouwen", "buiten-wittevrouwen", "oudwijk"],
        distance_to_station_km=1.8,
        lat_center=52.0956,
        lon_center=5.1355,
    ),
    NeighborhoodConfig(
        name="Hoograven",
        slugs=["oud-hoograven-noord", "oud-hoograven-zuid", "nieuw-hoograven"],
        distance_to_station_km=2.8,
        lat_center=52.0749,
        lon_center=5.1194,
    ),
    NeighborhoodConfig(
        name="Kanaleneiland",
        slugs=["kanaleneiland-noord", "kanaleneiland-zuid"],
        distance_to_station_km=3.5,
        lat_center=52.0664,
        lon_center=5.0941,
    ),
    NeighborhoodConfig(
        name="Overvecht",
        slugs=["overvecht-noord", "overvecht-zuid"],
        distance_to_station_km=4.0,
        lat_center=52.1169,
        lon_center=5.1159,
    ),
    NeighborhoodConfig(
        name="Leidsche Rijn",
        slugs=["leidsche-rijn-centrum", "vleuterweide", "de-wetering"],
        distance_to_station_km=5.0,
        lat_center=52.0893,
        lon_center=5.0476,
    ),
    NeighborhoodConfig(
        name="Vleuten-De Meern",
        slugs=["vleuten", "de-meern-noord", "de-meern-zuid"],
        distance_to_station_km=7.5,
        lat_center=52.1008,
        lon_center=5.0118,
    ),
    NeighborhoodConfig(
        name="Zuilen/Ondiep",
        slugs=["zuilen", "ondiep"],
        distance_to_station_km=2.5,
        lat_center=52.1080,
        lon_center=5.0921,
    ),
    NeighborhoodConfig(
        name="Rivierenwijk/Dichterswijk",
        slugs=["rivierenwijk", "dichterswijk"],
        distance_to_station_km=1.5,
        lat_center=52.0837,
        lon_center=5.1056,
    ),
    NeighborhoodConfig(
        name="Tuinwijk",
        slugs=["tuinwijk-oost", "tuinwijk-west"],
        distance_to_station_km=1.8,
        lat_center=52.0960,
        lon_center=5.1042,
    ),
    NeighborhoodConfig(
        name="Abstede",
        slugs=["abstede"],
        distance_to_station_km=2.0,
        lat_center=52.0821,
        lon_center=5.1348,
    ),
]

SLUG_TO_NEIGHBORHOOD: dict[str, str] = {
    slug: n.name for n in NEIGHBORHOODS for slug in n.slugs
}

NEIGHBORHOOD_BY_NAME: dict[str, NeighborhoodConfig] = {
    n.name: n for n in NEIGHBORHOODS
}
