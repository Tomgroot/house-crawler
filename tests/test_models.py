from datetime import datetime

from db.models import Listing, PriceHistory


def test_upsert_creates_single_listing(db_session, sample_listings):
    """Inserting the same funda_id twice should still result in one listing row."""
    count = db_session.query(Listing).filter_by(funda_id="10000001").count()
    assert count == 1


def test_all_fixtures_loaded(db_session, sample_listings):
    assert db_session.query(Listing).count() == 5


def test_sold_listing_has_sold_date(db_session, sample_listings):
    sold = db_session.query(Listing).filter_by(funda_id="10000003").first()
    assert sold.status == "sold"
    assert sold.sold_date is not None
    assert sold.sold_price == 290000


def test_price_per_m2_computed(db_session, sample_listings):
    listing = db_session.query(Listing).filter_by(funda_id="10000001").first()
    assert listing.price_per_m2 == 5000.0


def test_neighborhood_linked(db_session, sample_listings):
    listing = db_session.query(Listing).filter_by(funda_id="10000002").first()
    assert listing.neighborhood is not None
    assert listing.neighborhood.name == "Lombok"


def test_price_history_can_be_added(db_session, sample_listings):
    listing = db_session.query(Listing).filter_by(funda_id="10000001").first()
    db_session.add(PriceHistory(
        listing_id=listing.id,
        recorded_at=datetime.utcnow(),
        price=450000,
        status="for_sale",
    ))
    db_session.commit()
    history = db_session.query(PriceHistory).filter_by(listing_id=listing.id).all()
    assert len(history) == 1
