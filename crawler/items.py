import re
from datetime import date, datetime
from typing import Literal, Optional

import scrapy
from pydantic import BaseModel, Field, field_validator, model_validator


class RawListingItem(scrapy.Item):
    funda_id = scrapy.Field()
    url = scrapy.Field()
    address = scrapy.Field()
    postal_code = scrapy.Field()
    city = scrapy.Field()
    price_raw = scrapy.Field()
    size_raw = scrapy.Field()
    rooms_raw = scrapy.Field()
    listing_date_raw = scrapy.Field()
    days_on_market_raw = scrapy.Field()
    price_reduction_raw = scrapy.Field()
    property_type_raw = scrapy.Field()
    build_year_raw = scrapy.Field()
    energy_label_raw = scrapy.Field()
    status = scrapy.Field()       # "for_sale" or "sold"
    sold_date_raw = scrapy.Field()
    sold_price_raw = scrapy.Field()
    neighborhood_hint = scrapy.Field()  # logical neighborhood name from spider
    scraped_at = scrapy.Field()


def _parse_dutch_price(raw: str | None) -> int | None:
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def _parse_float(raw: str | None) -> float | None:
    if not raw:
        return None
    digits = re.sub(r"[^\d.,]", "", raw).replace(",", ".")
    try:
        return float(digits.split(".")[0] + ("." + digits.split(".")[-1] if "." in digits else ""))
    except ValueError:
        return None


def _parse_date_nl(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    months = {
        "januari": 1, "februari": 2, "maart": 3, "april": 4,
        "mei": 5, "juni": 6, "juli": 7, "augustus": 8,
        "september": 9, "oktober": 10, "november": 11, "december": 12,
    }
    parts = raw.lower().split()
    if len(parts) == 3:
        try:
            return date(int(parts[2]), months.get(parts[1], 0), int(parts[0]))
        except (ValueError, KeyError):
            pass
    # try ISO
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


class ListingValidator(BaseModel):
    funda_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    address: Optional[str] = None
    postal_code: Optional[str] = None
    price: Optional[int] = None
    size_m2: Optional[float] = None
    price_per_m2: Optional[float] = None
    num_rooms: Optional[int] = None
    num_bedrooms: Optional[int] = None
    listing_date: Optional[date] = None
    days_on_market: Optional[int] = None
    price_reduction_pct: Optional[float] = None
    property_type: Literal["house", "apartment", "unknown"] = "unknown"
    build_year: Optional[int] = None
    energy_label: Optional[str] = None
    status: Literal["for_sale", "sold"] = "for_sale"
    sold_date: Optional[date] = None
    sold_price: Optional[int] = None
    neighborhood_hint: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("price", mode="before")
    @classmethod
    def parse_price(cls, v):
        return _parse_dutch_price(str(v)) if v is not None else None

    @field_validator("sold_price", mode="before")
    @classmethod
    def parse_sold_price(cls, v):
        return _parse_dutch_price(str(v)) if v is not None else None

    @field_validator("size_m2", mode="before")
    @classmethod
    def parse_size(cls, v):
        return _parse_float(str(v)) if v is not None else None

    @field_validator("num_rooms", "num_bedrooms", mode="before")
    @classmethod
    def parse_int(cls, v):
        if v is None:
            return None
        m = re.search(r"\d+", str(v))
        return int(m.group()) if m else None

    @field_validator("listing_date", "sold_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, date):
            return v
        return _parse_date_nl(str(v))

    @field_validator("property_type", mode="before")
    @classmethod
    def map_type(cls, v):
        if v is None:
            return "unknown"
        mapping = {"huis": "house", "woonhuis": "house", "appartement": "apartment", "apartment": "apartment"}
        return mapping.get(str(v).lower().strip(), "unknown")

    @field_validator("price_reduction_pct", mode="before")
    @classmethod
    def parse_reduction(cls, v):
        if v is None:
            return None
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", str(v))
        if m:
            return float(m.group(1).replace(",", "."))
        return None

    @field_validator("build_year", mode="before")
    @classmethod
    def parse_build_year(cls, v):
        if v is None:
            return None
        m = re.search(r"\d{4}", str(v))
        return int(m.group()) if m else None

    @model_validator(mode="after")
    def compute_price_per_m2(self):
        if self.price and self.size_m2 and self.size_m2 > 0:
            self.price_per_m2 = round(self.price / self.size_m2, 2)
        return self
