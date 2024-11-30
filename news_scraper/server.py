from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
from threading import Thread
from typing import override

from news_scraper.scraper import NewsScraper


_LOGGER = logging.getLogger()


class NewsServer(Thread):
    scraper: NewsScraper
    http_addr: tuple[str, int]

    def __init__(self, scraper: NewsScraper, http_addr: tuple[str, int]):
        super().__init__(daemon=True)
        self.scraper = scraper
        self.http_addr = http_addr

    @override
    def run(self):
        scraper = self.scraper
        class HTTPHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != '/news.wav':
                    self.send_response(404) # Not Found
                    self.end_headers()
                    return

                news = scraper.get_news()

                if news:
                    self.send_response(200) # OK
                    self.send_header('Content-Type', 'audio/wav')
                    self.send_header('Content-Disposition', 'attachment; filename="news.wav"')
                    self.send_header('Content-Length', str(len(news)))
                    self.end_headers()
                    self.wfile.write(news)
                else:
                    self.send_response(503) # Service Unavailable
                    self.send_header('Content-Length', '0')
                    self.end_headers()

        _LOGGER.info('starting HTTP server on %s', self.http_addr)
        server = HTTPServer(self.http_addr, HTTPHandler)
        server.serve_forever()
