import json
import logging
import re
from datetime import datetime

import scrapy

from config.postal_codes import resolve_neighborhood
from crawler.items import RawListingItem

logger = logging.getLogger(__name__)

_FUNDA_ID_RE = re.compile(r"/(\d{6,9})/?$")


def _resolve(data: list, idx):
    """Dereference a single index in Nuxt's reviver format."""
    if idx is None or (isinstance(idx, int) and idx < 0):
        return None
    if not isinstance(idx, int):
        return idx
    item = data[idx]
    if (
        isinstance(item, list)
        and len(item) == 2
        and isinstance(item[0], str)
        and item[0] in ("Ref", "Reactive", "ShallowReactive", "EmptyRef", "Set")
    ):
        return _resolve(data, item[1])
    if isinstance(item, dict):
        return {k: _resolve(data, v) if isinstance(v, int) else v for k, v in item.items()}
    if isinstance(item, list):
        return [_resolve(data, i) if isinstance(i, int) else i for i in item]
    return item


def _parse_embedded_listings(html: str) -> tuple[list[dict], int]:
    """Extract listings from the Nuxt SSR inline JSON blob."""
    match = re.search(
        r'<script type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL
    )
    if not match:
        return [], 0

    data = json.loads(match.group(1))

    search_state = None
    for item in data:
        if isinstance(item, dict) and "listings" in item and "totalListingsCount" in item:
            search_state = item
            break

    if search_state is None:
        return [], 0

    total = _resolve(data, search_state["totalListingsCount"]) or 0
    # _resolve recursively resolves list items, so this is already a list of dicts
    listings = _resolve(data, search_state["listings"]) or []
    return [l for l in listings if isinstance(l, dict)], total


class FundaForSaleSpider(scrapy.Spider):
    name = "funda_forsale"
    custom_settings = {
        "CLOSESPIDER_ERRORCOUNT": 5,
    }

    def __init__(self, max_pages: int = 20, neighborhoods: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        # Optional filter: only store listings whose postal code resolves to one of these neighborhoods
        self.filter_names = {n.strip() for n in neighborhoods.split(",") if n.strip()} if neighborhoods else set()

    async def start(self):
        yield scrapy.Request(
            self._search_url(page=1),
            callback=self.parse_search_page,
            cb_kwargs={"page": 1},
        )

    @staticmethod
    def _search_url(page: int) -> str:
        base = "https://www.funda.nl/koop/utrecht/"
        return base if page == 1 else f"{base}p{page}/"

    def parse_search_page(self, response, page: int):
        listings, total = _parse_embedded_listings(response.text)

        logger.info(
            "Utrecht city-wide page %d: %d listings (total %s)",
            page, len(listings), total,
        )

        for listing in listings:
            item = self._listing_to_item(listing)
            if item is None:
                continue
            if self.filter_names:
                nbhd = resolve_neighborhood(item.get("postal_code", ""))
                if nbhd not in self.filter_names:
                    continue
            yield item

        if listings and page < self.max_pages:
            yield scrapy.Request(
                self._search_url(page + 1),
                callback=self.parse_search_page,
                cb_kwargs={"page": page + 1},
            )

    @staticmethod
    def _listing_to_item(listing: dict) -> RawListingItem | None:
        detail_url = listing.get("object_detail_page_relative_url", "")
        m = _FUNDA_ID_RE.search(detail_url)
        if not m:
            return None
        funda_id = m.group(1)

        address_obj = listing.get("address") or {}
        street = address_obj.get("street_name", "")
        house_no = address_obj.get("house_number", "")
        address_str = f"{street} {house_no}".strip() if street else ""
        postal_code = address_obj.get("postal_code", "")
        city = address_obj.get("city", "Utrecht")

        price_obj = listing.get("price") or {}
        selling_prices = price_obj.get("selling_price") or []
        price_raw = str(selling_prices[0]) if selling_prices else None

        floor_areas = listing.get("floor_area") or []
        size_raw = str(floor_areas[0]) if floor_areas else None

        item = RawListingItem()
        item["funda_id"] = funda_id
        item["url"] = f"https://www.funda.nl{detail_url}"
        item["address"] = address_str
        item["postal_code"] = postal_code
        item["city"] = city
        item["price_raw"] = price_raw
        item["size_raw"] = size_raw
        item["rooms_raw"] = str(listing.get("number_of_rooms")) if listing.get("number_of_rooms") else None
        item["energy_label_raw"] = listing.get("energy_label")
        item["property_type_raw"] = listing.get("object_type")
        item["listing_date_raw"] = listing.get("publish_date")
        item["status"] = "for_sale"
        item["neighborhood_hint"] = resolve_neighborhood(postal_code)
        item["scraped_at"] = datetime.utcnow()
        return item
