import json
import logging
import re
from datetime import datetime

import scrapy

from crawler.items import RawListingItem

logger = logging.getLogger(__name__)

_FUNDA_ID_RE = re.compile(r"/(\d{6,9})/?$")

_BASE_FOR_SALE = 'https://www.funda.nl/zoeken/koop?selected_area=[%22utrecht%22]'
_BASE_SOLD = 'https://www.funda.nl/zoeken/koop?selected_area=[%22utrecht%22]&availability=[%22unavailable%22]'


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
    listings = _resolve(data, search_state["listings"]) or []
    return [l for l in listings if isinstance(l, dict)], total


class FundaSpider(scrapy.Spider):
    name = "funda"
    custom_settings = {
        "CLOSESPIDER_ERRORCOUNT": 5,
    }

    def __init__(self, mode: str = "for_sale", max_pages: int = 20, start_page: int = 1, remember_page: str = "false", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode = mode
        self.max_pages = int(max_pages)
        self.start_page = int(start_page)
        self.remember_page = str(remember_page).lower() in ("1", "true", "yes")

    def _search_url(self, page: int) -> str:
        base = _BASE_SOLD if self.mode == "sold" else _BASE_FOR_SALE
        if page == 1:
            return base
        return f"{base}&search_result={page}"

    async def start(self):
        url = self._search_url(page=self.start_page)
        logger.info("Crawling %s (starting from page %d)", url, self.start_page)
        yield scrapy.Request(url, callback=self.parse_search_page, cb_kwargs={"page": self.start_page})

    def parse_search_page(self, response, page: int):
        logger.info("Fetching: %s", response.url)
        listings, total = _parse_embedded_listings(response.text)

        logger.info(
            "[%s] page=%d — found %d listings (total %s)",
            self.mode, page, len(listings), total,
        )

        if self.remember_page and listings:
            from crawler.state import save_page
            save_page(self.mode, page)

        for listing in listings:
            if self.mode == "sold":
                detail_url = listing.get("object_detail_page_relative_url", "")
                m = _FUNDA_ID_RE.search(detail_url)
                if not m:
                    continue
                funda_id = m.group(1)
                full_url = f"https://www.funda.nl{detail_url}"
                logger.info("  House: %s  %s", funda_id, detail_url)
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_sold_listing,
                    cb_kwargs={"listing": listing},
                )
            else:
                item = self._listing_to_item(listing)
                if item is not None:
                    logger.info("  House: %s  %s", item["funda_id"], item.get("address", ""))
                    yield item

        if listings and page < self.max_pages:
            next_url = self._search_url(page + 1)
            logger.info("Crawling %s", next_url)
            yield scrapy.Request(
                next_url,
                callback=self.parse_search_page,
                cb_kwargs={"page": page + 1},
            )

    def parse_sold_listing(self, response, listing: dict):
        item = self._listing_to_item(listing)
        if item is None:
            return
        item["status"] = "sold"
        item["sold_price_raw"] = self._xpath_dl(response, "Koopsom") or self._xpath_dl(response, "Verkocht voor")
        item["sold_date_raw"] = (
            self._xpath_dl(response, "Datum overdracht") or self._xpath_dl(response, "Overdrachtsdatum")
        )
        if not (item["sold_price_raw"] or item["sold_date_raw"]):
            item["status"] = "for_sale"
        yield item

    @staticmethod
    def _xpath_dl(response, label: str):
        value = response.xpath(
            f"//dt[contains(normalize-space(.), '{label}')]/following-sibling::dd[1]//text()"
        ).getall()
        text = " ".join(v.strip() for v in value if v.strip())
        return text or None

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
        item["scraped_at"] = datetime.utcnow()
        return item
