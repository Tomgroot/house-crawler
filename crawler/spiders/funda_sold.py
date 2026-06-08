import json
import logging
import re
from datetime import datetime

import scrapy

from config.neighborhoods import NEIGHBORHOODS
from crawler.items import RawListingItem
from crawler.spiders.funda_forsale import FundaForSaleSpider

logger = logging.getLogger(__name__)

SOLD_URL_RE = re.compile(
    r"funda\.nl(?:/en)?/(?:koop|detail/koop/verkocht)/utrecht/(?:huis|appartement)-(\d{8})", re.IGNORECASE
)


class FundaSoldSpider(scrapy.Spider):
    name = "funda_sold"
    custom_settings = {
        "CLOSESPIDER_ERRORCOUNT": 5,
    }

    def __init__(self, max_pages: int = 10, neighborhoods: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        filter_names = [n.strip() for n in neighborhoods.split(",") if n.strip()] if neighborhoods else []
        self.target_neighborhoods = [
            n for n in NEIGHBORHOODS if not filter_names or n.name in filter_names
        ]

    def start_requests(self):
        for nbhd in self.target_neighborhoods:
            for slug in nbhd.slugs:
                url = self._sold_url(slug, page=1)
                yield scrapy.Request(
                    url,
                    callback=self.parse_search_page,
                    meta={"playwright": True, "playwright_include_page": False},
                    cb_kwargs={"neighborhood": nbhd.name, "slug": slug, "page": 1},
                )

    @staticmethod
    def _sold_url(slug: str, page: int) -> str:
        base = f"https://www.funda.nl/koop/utrecht/{slug}/verkocht/sorteer-afmelddatum-af/"
        return base if page == 1 else f"{base}p{page}/"

    def parse_search_page(self, response, neighborhood: str, slug: str, page: int):
        links = set(
            response.css('a[data-test-id="object-image-link"]::attr(href)').getall()
            + response.css('a[data-test-id="object-title-link"]::attr(href)').getall()
            + response.css("a.search-result__header-title-col::attr(href)").getall()
        )

        found = 0
        for href in links:
            m = SOLD_URL_RE.search(href)
            if m:
                funda_id = m.group(1)
                full_url = response.urljoin(href)
                found += 1
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_listing,
                    meta={"playwright": True, "playwright_include_page": False},
                    cb_kwargs={"neighborhood": neighborhood, "funda_id": funda_id},
                )

        logger.info("Sold: neighborhood %s slug %s page %d: %d listings", neighborhood, slug, page, found)

        if found > 0 and page < self.max_pages:
            yield scrapy.Request(
                self._sold_url(slug, page + 1),
                callback=self.parse_search_page,
                meta={"playwright": True, "playwright_include_page": False},
                cb_kwargs={"neighborhood": neighborhood, "slug": slug, "page": page + 1},
            )

    def parse_listing(self, response, neighborhood: str, funda_id: str):
        item = RawListingItem()
        item["funda_id"] = funda_id
        item["url"] = response.url
        item["status"] = "sold"
        item["neighborhood_hint"] = neighborhood
        item["scraped_at"] = datetime.utcnow()

        ld_json = FundaForSaleSpider._extract_ld_json(response)
        if ld_json:
            address = ld_json.get("address", {})
            item["address"] = ld_json.get("name") or (
                f"{address.get('streetAddress', '')} {address.get('addressLocality', '')}".strip()
            )
            item["postal_code"] = address.get("postalCode", "").replace(" ", "")[:6]
            item["city"] = address.get("addressLocality", "Utrecht")
            item["property_type_raw"] = ld_json.get("@type", "")

        if not item.get("address"):
            item["address"] = response.css("h1.object-header__title::text").get("").strip()

        _dl = FundaForSaleSpider._xpath_dl

        item["price_raw"] = _dl(response, "Vraagprijs") or _dl(response, "Koopsom")
        item["sold_price_raw"] = _dl(response, "Koopsom") or _dl(response, "Verkocht voor")
        item["sold_date_raw"] = _dl(response, "Datum overdracht") or _dl(response, "Overdrachtsdatum")
        item["size_raw"] = _dl(response, "Woonoppervlakte")
        item["rooms_raw"] = _dl(response, "Aantal kamers")
        item["build_year_raw"] = _dl(response, "Bouwjaar")
        item["energy_label_raw"] = _dl(response, "Energielabel")
        item["listing_date_raw"] = _dl(response, "Aangeboden sinds")
        item["property_type_raw"] = item.get("property_type_raw") or _dl(response, "Soort woonhuis")

        yield item
