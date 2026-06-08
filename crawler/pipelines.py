import logging
from datetime import datetime

from pydantic import ValidationError

from config.postal_codes import resolve_neighborhood
from crawler.items import ListingValidator, RawListingItem
from db.engine import SessionLocal
from db.models import CrawlRun, Listing, Neighborhood, PriceHistory

logger = logging.getLogger(__name__)


class ValidationPipeline:
    def process_item(self, item: RawListingItem, spider=None):
        raw = dict(item)
        try:
            validated = ListingValidator(
                funda_id=raw.get("funda_id", ""),
                url=raw.get("url", ""),
                address=raw.get("address"),
                postal_code=raw.get("postal_code"),
                price=raw.get("price_raw"),
                size_m2=raw.get("size_raw"),
                num_rooms=raw.get("rooms_raw"),
                listing_date=raw.get("listing_date_raw"),
                price_reduction_pct=raw.get("price_reduction_raw"),
                property_type=raw.get("property_type_raw"),
                build_year=raw.get("build_year_raw"),
                energy_label=raw.get("energy_label_raw"),
                status=raw.get("status", "for_sale"),
                sold_date=raw.get("sold_date_raw"),
                sold_price=raw.get("sold_price_raw"),
                neighborhood_hint=raw.get("neighborhood_hint"),
                scraped_at=raw.get("scraped_at", datetime.utcnow()),
            )
            item["_validated"] = validated
            return item
        except ValidationError as e:
            logger.warning("Validation failed for %s: %s", raw.get("funda_id"), e)
            raise


class NeighborhoodPipeline:
    def open_spider(self, spider=None):
        self._session = SessionLocal()
        self._cache: dict[str, int | None] = {}

    def close_spider(self, spider=None):
        self._session.close()

    def process_item(self, item: RawListingItem, spider=None):
        validated: ListingValidator = item.get("_validated")
        if not validated:
            return item

        neighborhood_name = validated.neighborhood_hint
        if not neighborhood_name and validated.postal_code:
            neighborhood_name = resolve_neighborhood(validated.postal_code)

        if neighborhood_name:
            if neighborhood_name not in self._cache:
                row = self._session.query(Neighborhood).filter_by(name=neighborhood_name).first()
                self._cache[neighborhood_name] = row.id if row else None
            item["_neighborhood_id"] = self._cache[neighborhood_name]
        else:
            item["_neighborhood_id"] = None

        return item


class DatabasePipeline:
    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        obj.crawler = crawler
        return obj

    def open_spider(self, spider=None):
        self._session = SessionLocal()
        spider_name = (spider or self.crawler.spider).name
        self._crawl_run = CrawlRun(
            started_at=datetime.utcnow(),
            spider_name=spider_name,
            status="running",
        )
        self._session.add(self._crawl_run)
        self._session.commit()

    def close_spider(self, spider=None):
        self._crawl_run.finished_at = datetime.utcnow()
        self._crawl_run.status = "completed"
        self._session.commit()
        self._session.close()

    def process_item(self, item: RawListingItem, spider=None):
        validated: ListingValidator | None = item.get("_validated")
        if not validated:
            return item

        neighborhood_id: int | None = item.get("_neighborhood_id")
        now = datetime.utcnow()

        existing = self._session.query(Listing).filter_by(funda_id=validated.funda_id).first()

        if existing is None:
            listing = Listing(
                funda_id=validated.funda_id,
                url=validated.url,
                address=validated.address,
                postal_code=validated.postal_code,
                neighborhood_id=neighborhood_id,
                price=validated.price,
                size_m2=validated.size_m2,
                price_per_m2=validated.price_per_m2,
                num_rooms=validated.num_rooms,
                num_bedrooms=validated.num_bedrooms,
                property_type=validated.property_type,
                build_year=validated.build_year,
                energy_label=validated.energy_label,
                status=validated.status,
                listing_date=validated.listing_date,
                sold_date=validated.sold_date,
                sold_price=validated.sold_price,
                first_seen_at=now,
                last_seen_at=now,
                is_active=True,
            )
            self._session.add(listing)
            self._session.flush()
            self._crawl_run.listings_new = (self._crawl_run.listings_new or 0) + 1
        else:
            price_changed = existing.price != validated.price
            listing = existing
            listing.last_seen_at = now
            listing.is_active = True
            listing.status = validated.status
            if validated.sold_date:
                listing.sold_date = validated.sold_date
            if validated.sold_price:
                listing.sold_price = validated.sold_price
            if neighborhood_id and not listing.neighborhood_id:
                listing.neighborhood_id = neighborhood_id
            if price_changed:
                listing.price = validated.price
                listing.price_per_m2 = validated.price_per_m2
            self._crawl_run.listings_updated = (self._crawl_run.listings_updated or 0) + 1

        self._session.add(
            PriceHistory(
                listing_id=listing.id,
                recorded_at=now,
                price=validated.price,
                price_reduction_pct=validated.price_reduction_pct,
                status=validated.status,
                crawl_run_id=self._crawl_run.id,
            )
        )
        self._crawl_run.listings_found = (self._crawl_run.listings_found or 0) + 1
        self._session.commit()
        return item
