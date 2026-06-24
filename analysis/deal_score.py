import logging

import numpy as np
import pandas as pd
from sqlalchemy import text

from db.engine import get_engine

logger = logging.getLogger(__name__)

MIN_COMPARABLES = 5
SIZE_RANGE_PCT = 0.30
DEAL_THRESHOLD_DEFAULT = 0.15
MIN_SIZE_M2_DEFAULT = 60.0


def _load_active_for_sale() -> pd.DataFrame:
    sql = """
        SELECT
            l.funda_id, l.url, l.address, l.postal_code,
            n.name AS neighborhood, n.distance_to_station_km,
            l.price, l.size_m2, l.price_per_m2,
            l.num_rooms, l.first_seen_at
        FROM listings l
        LEFT JOIN neighborhoods n ON l.neighborhood_id = n.id
        WHERE l.status = 'for_sale'
          AND l.is_active = 1
          AND l.price_per_m2 IS NOT NULL
    """
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn)


def _find_comparables(listing: pd.Series, pool: pd.DataFrame) -> pd.DataFrame:
    """Return listings from pool comparable to this one by size and location."""
    size = listing["size_m2"]
    funda_id = listing["funda_id"]
    nbhd = listing.get("neighborhood")

    candidates = pool[pool["funda_id"] != funda_id].copy()

    if size and not np.isnan(float(size)):
        lo, hi = size * (1 - SIZE_RANGE_PCT), size * (1 + SIZE_RANGE_PCT)
        candidates = candidates[candidates["size_m2"].between(lo, hi)]

    if nbhd:
        same_nbhd = candidates[candidates["neighborhood"] == nbhd]
        if len(same_nbhd) >= MIN_COMPARABLES:
            return same_nbhd

    dist = listing.get("distance_to_station_km")
    if dist is not None and not np.isnan(float(dist)):
        nearby = candidates[
            candidates["distance_to_station_km"].between(float(dist) - 1.0, float(dist) + 1.0)
        ]
        if len(nearby) >= MIN_COMPARABLES:
            return nearby

    return candidates


def score_listing(
    listing: pd.Series,
    pool: pd.DataFrame,
    deal_threshold: float = DEAL_THRESHOLD_DEFAULT,
    min_size_m2: float = MIN_SIZE_M2_DEFAULT,
) -> dict | None:
    """Return deal metadata if the listing is significantly underpriced, else None."""
    ppm2 = listing.get("price_per_m2")
    size = listing.get("size_m2")

    if ppm2 is None or (isinstance(ppm2, float) and np.isnan(ppm2)):
        return None
    if size is None or (isinstance(size, float) and np.isnan(size)) or float(size) < min_size_m2:
        return None

    comparables = _find_comparables(listing, pool)
    if len(comparables) < MIN_COMPARABLES:
        return None

    median_ppm2 = comparables["price_per_m2"].median()
    discount = (median_ppm2 - float(ppm2)) / median_ppm2

    if discount < deal_threshold:
        return None

    return {
        "discount_pct": round(discount * 100, 1),
        "listing_price_per_m2": int(round(float(ppm2))),
        "median_comparable_price_per_m2": int(round(median_ppm2)),
        "num_comparables": len(comparables),
    }


def find_deals(
    since_dt=None,
    deal_threshold: float = DEAL_THRESHOLD_DEFAULT,
    min_size_m2: float = MIN_SIZE_M2_DEFAULT,
) -> list[dict]:
    """Find for-sale listings that are significantly cheaper than comparable houses."""
    pool = _load_active_for_sale()
    if pool.empty:
        logger.warning("No active for-sale listings found.")
        return []

    candidates = pool
    if since_dt is not None:
        since_ts = pd.Timestamp(since_dt)
        candidates = pool[pd.to_datetime(pool["first_seen_at"]) >= since_ts]

    if candidates.empty:
        logger.info("No new listings since %s.", since_dt)
        return []

    deals = []
    for _, listing in candidates.iterrows():
        result = score_listing(listing, pool, deal_threshold, min_size_m2)
        if result is None:
            continue
        deals.append(
            {
                "funda_id": listing["funda_id"],
                "address": listing.get("address") or "",
                "url": listing.get("url") or "",
                "neighborhood": listing.get("neighborhood") or "",
                "price": int(listing["price"]) if listing.get("price") else None,
                "size_m2": float(listing["size_m2"]) if listing.get("size_m2") else None,
                "distance_to_station_km": listing.get("distance_to_station_km"),
                **result,
            }
        )

    return deals
