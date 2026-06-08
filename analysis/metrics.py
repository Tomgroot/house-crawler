import calendar
import logging
from datetime import date, datetime

import numpy as np
from sqlalchemy.orm import Session

from db.engine import SessionLocal
from db.models import Listing, Neighborhood, NeighborhoodSnapshot

logger = logging.getLogger(__name__)


def _was_active_in_month(listing: Listing, start: date, end: date) -> bool:
    """True if the listing was on the market at any point during [start, end]."""
    # Use listing_date if available, fall back to first_seen_at date
    known_since: date | None = listing.listing_date or (
        listing.first_seen_at.date() if listing.first_seen_at else None
    )
    if known_since is not None and known_since > end:
        return False  # not yet on market
    # Exclude if sold before this month started
    if listing.sold_date and listing.sold_date < start:
        return False
    return True


def compute_snapshot(session: Session, neighborhood: Neighborhood, month: date) -> NeighborhoodSnapshot | None:
    """Compute or update the monthly snapshot for a single neighborhood."""
    month_start = date(month.year, month.month, 1)
    last_day = calendar.monthrange(month.year, month.month)[1]
    month_end = date(month.year, month.month, last_day)

    all_listings = (
        session.query(Listing)
        .filter(Listing.neighborhood_id == neighborhood.id)
        .all()
    )

    listings = [l for l in all_listings if _was_active_in_month(l, month_start, month_end)]

    if not listings:
        return None

    prices_per_m2 = [l.price_per_m2 for l in listings if l.price_per_m2]
    sold_this_month = [
        l for l in listings
        if l.sold_date
        and l.sold_date.year == month.year
        and l.sold_date.month == month.month
    ]
    active = [l for l in listings if l.status == "for_sale"]

    # Days on market: use listing_date → sold_date (or end of month)
    doms = []
    for l in listings:
        start_date = l.listing_date or (l.first_seen_at.date() if l.first_seen_at else None)
        if start_date is None:
            continue
        end_date = l.sold_date if l.sold_date else month_end
        dom = (end_date - start_date).days
        if 0 <= dom <= 730:
            doms.append(dom)

    _ = [l for l in listings if l.price_per_m2 is not None]  # kept for future reduction stats

    snapshot = NeighborhoodSnapshot(
        neighborhood_id=neighborhood.id,
        snapshot_month=month_start,
        median_price_per_m2=float(np.median(prices_per_m2)) if prices_per_m2 else None,
        avg_price_per_m2=float(np.mean(prices_per_m2)) if prices_per_m2 else None,
        avg_days_on_market=float(np.mean(doms)) if doms else None,
        transaction_volume=len(sold_this_month),
        active_listings=len(active),
        price_reduction_frequency=None,  # requires price_history join — skip for now
        avg_price_reduction_pct=None,
        computed_at=datetime.utcnow(),
    )
    return snapshot


def compute_all_snapshots(month: date | None = None) -> int:
    """Compute snapshots for all neighborhoods for the given month (defaults to current)."""
    if month is None:
        today = datetime.utcnow().date()
        month = date(today.year, today.month, 1)

    session = SessionLocal()
    try:
        neighborhoods = session.query(Neighborhood).all()
        count = 0
        for nbhd in neighborhoods:
            snapshot = compute_snapshot(session, nbhd, month)
            if snapshot is None:
                continue

            existing = (
                session.query(NeighborhoodSnapshot)
                .filter_by(neighborhood_id=nbhd.id, snapshot_month=date(month.year, month.month, 1))
                .first()
            )
            if existing:
                existing.median_price_per_m2 = snapshot.median_price_per_m2
                existing.avg_price_per_m2 = snapshot.avg_price_per_m2
                existing.avg_days_on_market = snapshot.avg_days_on_market
                existing.transaction_volume = snapshot.transaction_volume
                existing.active_listings = snapshot.active_listings
                existing.computed_at = snapshot.computed_at
            else:
                session.add(snapshot)
            count += 1

        session.commit()
        logger.info("Computed %d snapshots for %s-%02d", count, month.year, month.month)
        return count
    finally:
        session.close()
