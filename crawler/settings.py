import os

from dotenv import load_dotenv

load_dotenv()

BOT_NAME = "house-crawler"
SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# curl_cffi-backed handler bypasses Akamai bot detection at TLS fingerprint level
DOWNLOAD_HANDLERS = {
    "https": "crawler.handlers.curl_cffi_handler.CurlCffiDownloadHandler",
    "http": "crawler.handlers.curl_cffi_handler.CurlCffiDownloadHandler",
}

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
