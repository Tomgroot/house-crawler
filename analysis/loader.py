from datetime import date

import pandas as pd
from sqlalchemy import text

from db.engine import get_engine


def load_listings(
    neighborhood: str | None = None,
    status: str | None = None,
    since: date | None = None,
) -> pd.DataFrame:
    """Load listings joined with neighborhood data."""
    sql = """
        SELECT
            l.id, l.funda_id, l.address, l.postal_code,
            n.name AS neighborhood, n.distance_to_station_km,
            l.price, l.size_m2, l.price_per_m2,
            l.num_rooms, l.num_bedrooms, l.property_type,
            l.build_year, l.energy_label,
            l.status, l.listing_date, l.sold_date, l.sold_price,
            l.first_seen_at, l.last_seen_at, l.is_active
        FROM listings l
        LEFT JOIN neighborhoods n ON l.neighborhood_id = n.id
        WHERE 1=1
    """
    params: dict = {}

    if neighborhood:
        sql += " AND n.name = :neighborhood"
        params["neighborhood"] = neighborhood
    if status:
        sql += " AND l.status = :status"
        params["status"] = status
    if since:
        sql += " AND l.first_seen_at >= :since"
        params["since"] = since.isoformat()

    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def load_snapshots(neighborhood: str | None = None) -> pd.DataFrame:
    """Load monthly neighborhood snapshots joined with neighborhood metadata."""
    sql = """
        SELECT
            n.name AS neighborhood, n.distance_to_station_km,
            s.snapshot_month,
            s.median_price_per_m2, s.avg_price_per_m2,
            s.avg_days_on_market, s.transaction_volume,
            s.active_listings, s.price_reduction_frequency,
            s.avg_price_reduction_pct
        FROM neighborhood_snapshots s
        JOIN neighborhoods n ON s.neighborhood_id = n.id
    """
    params: dict = {}
    if neighborhood:
        sql += " WHERE n.name = :neighborhood"
        params["neighborhood"] = neighborhood
    sql += " ORDER BY n.name, s.snapshot_month"

    with get_engine().connect() as conn:
        df = pd.read_sql(text(sql), conn, params=params)

    df["snapshot_month"] = pd.to_datetime(df["snapshot_month"])
    return df


def load_neighborhoods() -> pd.DataFrame:
    """Load all neighborhood metadata."""
    sql = "SELECT * FROM neighborhoods ORDER BY name"
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn)
