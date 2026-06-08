import os

from dotenv import load_dotenv

load_dotenv()

BOT_NAME = "house-crawler"
SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Playwright for JavaScript rendering / bot evasion
DOWNLOAD_HANDLERS = {
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30_000

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Polite crawling
DOWNLOAD_DELAY = 4.0
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = 1
CONCURRENT_REQUESTS_PER_DOMAIN = 1
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3
AUTOTHROTTLE_MAX_DELAY = 30
AUTOTHROTTLE_TARGET_CONCURRENCY = 0.5

ROBOTSTXT_OBEY = False
COOKIES_ENABLED = True

DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "crawler.middlewares.user_agent.RotatingUserAgentMiddleware": 400,
}

ITEM_PIPELINES = {
    "crawler.pipelines.ValidationPipeline": 100,
    "crawler.pipelines.NeighborhoodPipeline": 200,
    "crawler.pipelines.DatabasePipeline": 300,
}

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
FEED_EXPORT_ENCODING = "utf-8"
