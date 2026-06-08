from datetime import date, datetime

import pytest

from db.models import Listing, Neighborhood, NeighborhoodSnapshot


def test_compute_snapshot_returns_correct_median(db_session, sample_listings):
    from analysis.metrics import compute_snapshot

    nbhd = db_session.query(Neighborhood).filter_by(name="Binnenstad").first()
    snapshot = compute_snapshot(db_session, nbhd, date(2024, 2, 1))
    # Binnenstad has one listing with price_per_m2 = 5000
    assert snapshot is not None
    assert snapshot.median_price_per_m2 == pytest.approx(5000.0)


def test_compute_snapshot_counts_active(db_session, sample_listings):
    from analysis.metrics import compute_snapshot

    nbhd = db_session.query(Neighborhood).filter_by(name="Binnenstad").first()
    snapshot = compute_snapshot(db_session, nbhd, date(2024, 2, 1))
    assert snapshot.active_listings == 1


def test_compute_snapshot_counts_sold_transactions(db_session, sample_listings):
    from analysis.metrics import compute_snapshot

    nbhd = db_session.query(Neighborhood).filter_by(name="Hoograven").first()
    snapshot = compute_snapshot(db_session, nbhd, date(2024, 1, 1))
    # funda_id 10000003 sold in January 2024
    assert snapshot.transaction_volume == 1


def test_compute_snapshot_no_listings_returns_none(db_session):
    from analysis.metrics import compute_snapshot

    nbhd = db_session.query(Neighborhood).filter_by(name="Kanaleneiland").first()
    snapshot = compute_snapshot(db_session, nbhd, date(2030, 1, 1))
    assert snapshot is None
