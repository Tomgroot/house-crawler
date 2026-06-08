import json
import logging
import re
from datetime import datetime
from urllib.parse import urlencode, quote

import scrapy

from config.neighborhoods import NEIGHBORHOODS
from crawler.items import RawListingItem

logger = logging.getLogger(__name__)

LISTING_URL_RE = re.compile(
    r"funda\.nl(?:/en)?/koop/utrecht/(?:huis|appartement)-(\d{8})", re.IGNORECASE
)


class FundaForSaleSpider(scrapy.Spider):
    name = "funda_forsale"
    custom_settings = {
        "CLOSESPIDER_ERRORCOUNT": 5,
    }

    def __init__(self, max_pages: int = 20, neighborhoods: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        filter_names = [n.strip() for n in neighborhoods.split(",") if n.strip()] if neighborhoods else []
        self.target_neighborhoods = [
            n for n in NEIGHBORHOODS if not filter_names or n.name in filter_names
        ]

    def start_requests(self):
        for nbhd in self.target_neighborhoods:
            for slug in nbhd.slugs:
                url = self._search_url(slug, page=1)
                yield scrapy.Request(
                    url,
                    callback=self.parse_search_page,
                    meta={"playwright": True, "playwright_include_page": False},
                    cb_kwargs={"neighborhood": nbhd.name, "slug": slug, "page": 1},
                    dont_filter=False,
                )

    @staticmethod
    def _search_url(slug: str, page: int) -> str:
        area = f'["utrecht/{slug}"]'
        params = {"selected_area": area}
        if page > 1:
            params["page"] = str(page)
        return f"https://www.funda.nl/zoeken/koop/?{urlencode(params)}"

    def parse_search_page(self, response, neighborhood: str, slug: str, page: int):
        links = set(
            response.css('a[data-test-id="object-image-link"]::attr(href)').getall()
            + response.css('a[data-test-id="object-title-link"]::attr(href)').getall()
        )

        found = 0
        for href in links:
            m = LISTING_URL_RE.search(href)
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

        logger.info("Neighborhood %s slug %s page %d: %d listings found", neighborhood, slug, page, found)

        if found > 0 and page < self.max_pages:
            next_url = self._search_url(slug, page + 1)
            yield scrapy.Request(
                next_url,
                callback=self.parse_search_page,
                meta={"playwright": True, "playwright_include_page": False},
                cb_kwargs={"neighborhood": neighborhood, "slug": slug, "page": page + 1},
            )

    def parse_listing(self, response, neighborhood: str, funda_id: str):
        item = RawListingItem()
        item["funda_id"] = funda_id
        item["url"] = response.url
        item["status"] = "for_sale"
        item["neighborhood_hint"] = neighborhood
        item["scraped_at"] = datetime.utcnow()

        # --- JSON-LD primary extraction ---
        ld_json = self._extract_ld_json(response)
        if ld_json:
            address = ld_json.get("address", {})
            item["address"] = ld_json.get("name") or (
                f"{address.get('streetAddress', '')} {address.get('addressLocality', '')}".strip()
            )
            item["postal_code"] = address.get("postalCode", "").replace(" ", "")[:6]
            item["city"] = address.get("addressLocality", "Utrecht")
            item["price_raw"] = str(ld_json.get("offers", {}).get("price", ""))
            item["property_type_raw"] = ld_json.get("@type", "")

        # --- XPath / CSS fallback ---
        if not item.get("address"):
            item["address"] = response.css("h1.object-header__title::text").get("").strip()

        if not item.get("postal_code"):
            pc_text = response.css("span.object-header__subtitle::text").get("") or ""
            m = re.search(r"\b(\d{4}\s*[A-Z]{2})\b", pc_text)
            if m:
                item["postal_code"] = m.group(1).replace(" ", "")

        item["price_raw"] = item.get("price_raw") or self._xpath_dl(response, "Vraagprijs")
        item["size_raw"] = self._xpath_dl(response, "Woonoppervlakte")
        item["rooms_raw"] = self._xpath_dl(response, "Aantal kamers")
        item["build_year_raw"] = self._xpath_dl(response, "Bouwjaar")
        item["energy_label_raw"] = self._xpath_dl(response, "Energielabel")
        item["listing_date_raw"] = self._xpath_dl(response, "Aangeboden sinds")
        item["property_type_raw"] = item.get("property_type_raw") or self._xpath_dl(response, "Soort woonhuis")

        # Price reduction from badge
        reduction_text = response.css("[data-test-id='price-reduction'] ::text").get("")
        item["price_reduction_raw"] = reduction_text.strip() or None

        yield item

    @staticmethod
    def _extract_ld_json(response) -> dict | None:
        for script in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(script)
                if isinstance(data, list):
                    data = next((d for d in data if d.get("@type") in ("Residence", "RealEstateListing")), None)
                if data and data.get("@type") in ("Residence", "RealEstateListing"):
                    return data
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    @staticmethod
    def _xpath_dl(response, label: str) -> str | None:
        value = response.xpath(
            f"//dt[contains(normalize-space(.), '{label}')]/following-sibling::dd[1]//text()"
        ).getall()
        text = " ".join(v.strip() for v in value if v.strip())
        return text or None
