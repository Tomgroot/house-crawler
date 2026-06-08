import json
import os
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from db.engine import Base
from db.models import CrawlRun, Listing, Neighborhood, NeighborhoodSnapshot


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="function")
def db_session():
    """In-memory SQLite session, rolled back after each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed neighborhoods
    for name, dist in [
        ("Binnenstad", 0.5),
        ("Lombok", 1.2),
        ("Hoograven", 2.8),
        ("Kanaleneiland", 3.5),
        ("Leidsche Rijn", 5.0),
    ]:
        session.add(Neighborhood(name=name, slug=name.lower().replace(" ", "-"),
                                  distance_to_station_km=dist))
    session.commit()

    yield session
    session.close()


@pytest.fixture(scope="function")
def sample_listings(db_session):
    """Load sample listings from fixtures JSON into the in-memory DB."""
    fixtures = json.loads((FIXTURES_DIR / "sample_listings.json").read_text())
    nbhd_map = {n.name: n.id for n in db_session.query(Neighborhood).all()}
    now = datetime.utcnow()

    listings = []
    for f in fixtures:
        listing = Listing(
            funda_id=f["funda_id"],
            url=f["url"],
            address=f["address"],
            postal_code=f["postal_code"],
            neighborhood_id=nbhd_map.get(f["neighborhood"]),
            price=f["price"],
            size_m2=f["size_m2"],
            price_per_m2=f["price_per_m2"],
            num_rooms=f["num_rooms"],
            num_bedrooms=f["num_bedrooms"],
            property_type=f["property_type"],
            build_year=f["build_year"],
            energy_label=f["energy_label"],
            status=f["status"],
            listing_date=date.fromisoformat(f["listing_date"]) if f["listing_date"] else None,
            sold_date=date.fromisoformat(f["sold_date"]) if f["sold_date"] else None,
            sold_price=f["sold_price"],
            first_seen_at=now,
            last_seen_at=now,
        )
        db_session.add(listing)
        listings.append(listing)

    db_session.commit()
    return listings
