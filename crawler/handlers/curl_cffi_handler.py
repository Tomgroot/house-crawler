from scrapy.http import HtmlResponse
from curl_cffi.requests import Session
from twisted.internet import threads


class CurlCffiDownloadHandler:
    """Scrapy download handler backed by curl_cffi, bypasses Akamai bot detection."""

    @classmethod
    def from_settings(cls, settings):
        return cls()

    def __init__(self):
        self._session = Session(impersonate="chrome124")

    def download_request(self, request, spider):
        return threads.deferToThread(self._fetch, request)

    def _fetch(self, request):
        headers = {
            k.decode(): v[0].decode()
            for k, v in request.headers.items()
        }
        r = self._session.request(
            method=request.method,
            url=request.url,
            headers=headers,
        )
        return HtmlResponse(
            url=request.url,
            status=r.status_code,
            body=r.content,
            encoding=r.encoding or "utf-8",
        )

    def close(self):
        pass
