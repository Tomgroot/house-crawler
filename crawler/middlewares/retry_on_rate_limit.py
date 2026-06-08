import logging
import time

from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

logger = logging.getLogger(__name__)

# Status codes that indicate rate-limiting or temporary unavailability
_RETRY_STATUSES = {429, 503}

# Base delay in seconds for the first retry; doubles each attempt
_BASE_BACKOFF = 30


class RateLimitRetryMiddleware(RetryMiddleware):
    """Extends Scrapy's built-in retry middleware to handle 429/503 with exponential backoff."""

    def process_response(self, request, response, spider=None):
        if response.status not in _RETRY_STATUSES:
            return response

        retry_after = self._parse_retry_after(response)
        attempt = request.meta.get("retry_times", 0)
        delay = retry_after if retry_after else min(_BASE_BACKOFF * (2 ** attempt), 300)

        logger.warning(
            "Got %d from %s — sleeping %.0fs before retry (attempt %d)",
            response.status,
            request.url,
            delay,
            attempt + 1,
        )
        time.sleep(delay)

        _spider = spider or self.crawler.spider
        reason = response_status_message(response.status)
        return self._retry(request, reason, _spider) or response

    def process_exception(self, request, exception, spider=None):
        return super().process_exception(request, exception, spider or self.crawler.spider)

    @staticmethod
    def _parse_retry_after(response) -> float | None:
        header = response.headers.get("Retry-After", b"").decode().strip()
        if not header:
            return None
        try:
            return float(header)
        except ValueError:
            return None
