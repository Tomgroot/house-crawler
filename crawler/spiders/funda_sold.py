import logging
from datetime import datetime

import scrapy

from config.postal_codes import resolve_neighborhood
from crawler.items import RawListingItem
from crawler.spiders.funda_forsale import (
    _FUNDA_ID_RE,
    _parse_embedded_listings,
    FundaForSaleSpider,
)

logger = logging.getLogger(__name__)


class FundaSoldSpider(scrapy.Spider):
    """
    Scrapes sold listings from Funda.

    Funda no longer SSR-renders sold-only search pages; this spider therefore
    scrapes the regular for-sale search with the /verkocht/ URL suffix (which
    the server still accepts) and relies on individual listing detail pages for
    the sold date / sold price fields.  Listings whose detail page indicates they
    are sold are stored with status="sold".
    """

    name = "funda_sold"
    custom_settings = {
        "CLOSESPIDER_ERRORCOUNT": 5,
    }

    def __init__(self, max_pages: int = 10, neighborhoods: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self.filter_names = {n.strip() for n in neighborhoods.split(",") if n.strip()} if neighborhoods else set()

    async def start(self):
        yield scrapy.Request(
            self._sold_url(page=1),
            callback=self.parse_search_page,
            cb_kwargs={"page": 1},
        )

    @staticmethod
    def _sold_url(page: int) -> str:
        base = "https://www.funda.nl/koop/utrecht/"
        return f"{base}verkocht/" if page == 1 else f"{base}p{page}/verkocht/"

    def parse_search_page(self, response, page: int):
        listings, total = _parse_embedded_listings(response.text)

        logger.info(
            "Sold: Utrecht city-wide page %d: %d listings (total %s)",
            page, len(listings), total,
        )

        for listing in listings:
            detail_url = listing.get("object_detail_page_relative_url", "")
            m = _FUNDA_ID_RE.search(detail_url)
            if not m:
                continue
            funda_id = m.group(1)
            if self.filter_names:
                postal = (listing.get("address") or {}).get("postal_code", "")
                nbhd = resolve_neighborhood(postal)
                if nbhd not in self.filter_names:
                    continue
            full_url = f"https://www.funda.nl{detail_url}"
            yield scrapy.Request(
                full_url,
                callback=self.parse_listing,
                cb_kwargs={"funda_id": funda_id, "listing": listing},
            )

        if listings and page < self.max_pages:
            yield scrapy.Request(
                self._sold_url(page + 1),
                callback=self.parse_search_page,
                cb_kwargs={"page": page + 1},
            )

    def parse_listing(self, response, funda_id: str, listing: dict):
        item = FundaForSaleSpider._listing_to_item(listing)
        if item is None:
            return
        item["status"] = "sold"

        _dl = self._xpath_dl
        item["sold_price_raw"] = _dl(response, "Koopsom") or _dl(response, "Verkocht voor")
        item["sold_date_raw"] = (
            _dl(response, "Datum overdracht") or _dl(response, "Overdrachtsdatum")
        )
        if item["sold_price_raw"] or item["sold_date_raw"]:
            item["status"] = "sold"
        else:
            item["status"] = "for_sale"
        yield item

    @staticmethod
    def _xpath_dl(response, label: str):
        value = response.xpath(
            f"//dt[contains(normalize-space(.), '{label}')]/following-sibling::dd[1]//text()"
        ).getall()
        text = " ".join(v.strip() for v in value if v.strip())
        return text or None
