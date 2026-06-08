"""Test the Pydantic validators and scoring sub-functions."""

import pytest

from crawler.items import ListingValidator


def test_price_parsing():
    v = ListingValidator(funda_id="1", url="http://x", price="€ 425.000 k.k.")
    assert v.price == 425000


def test_size_parsing():
    v = ListingValidator(funda_id="1", url="http://x", size_m2="87 m²")
    assert v.size_m2 == pytest.approx(87.0)


def test_price_per_m2_computed():
    v = ListingValidator(funda_id="1", url="http://x", price="€ 435.000", size_m2="87 m²")
    assert v.price_per_m2 == pytest.approx(5000.0, rel=0.01)


def test_property_type_mapping():
    v = ListingValidator(funda_id="1", url="http://x", property_type="huis")
    assert v.property_type == "house"

    v2 = ListingValidator(funda_id="1", url="http://x", property_type="appartement")
    assert v2.property_type == "apartment"

    v3 = ListingValidator(funda_id="1", url="http://x", property_type="garage")
    assert v3.property_type == "unknown"


def test_date_parsing_dutch():
    v = ListingValidator(funda_id="1", url="http://x", listing_date="15 januari 2024")
    from datetime import date
    assert v.listing_date == date(2024, 1, 15)


def test_price_reduction_parsing():
    v = ListingValidator(funda_id="1", url="http://x", price_reduction_pct="Prijs verlaagd met 5%")
    assert v.price_reduction_pct == pytest.approx(5.0)


def test_invalid_funda_id_raises():
    with pytest.raises(Exception):
        ListingValidator(funda_id="", url="")


def test_missing_optional_fields_ok():
    v = ListingValidator(funda_id="42", url="http://x")
    assert v.price is None
    assert v.size_m2 is None
    assert v.price_per_m2 is None
    assert v.property_type == "unknown"
    assert v.status == "for_sale"
