import logging
import sys
import tempfile
import time
from argparse import ArgumentParser
from pathlib import Path
from typing import Never, cast

from news_scraper.scraper import NewsScraper
from news_scraper.server import NewsServer
from news_scraper.source.haarlem import RadioHaarlemNewsSource
from news_scraper.source.npo2 import NPO2NewsSource
from news_scraper.source.sublime import SublimeNewsSource

NEWS_SOURCES = {
    "sublime": SublimeNewsSource(),
    "npo-radio2": NPO2NewsSource(),
    "haarlem": RadioHaarlemNewsSource(),
}

def main() -> Never:
    parser = ArgumentParser()

    parser.add_argument('--source', type=str, required=True,
                        help='News source. Choose from: ' + ','.join(NEWS_SOURCES.keys()))
    parser.add_argument('--http-bind', type=str, default='127.0.0.1')
    parser.add_argument('--http-port', type=int, default=43473)

    parser_dev = parser.add_argument_group('development options')
    parser_dev.add_argument('--persistent', action='store_true',
                        help='Store temporary data in persistent ./data instead of in /tmp')
    parser_dev.add_argument('--force-recording', type=str,
                        help='Path to an existing recording. This recording will be processed, then the program will exit immediately')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    source = NEWS_SOURCES[cast(str, args.source)]
    http_addr = (cast(str, args.http_bind), cast(int, args.http_port))

    with tempfile.TemporaryDirectory(prefix='news-scraper-') as tempdir:
        if args.persistent:
            # TODO configurable with --persistent value
            workdir = Path('./data').absolute()
            workdir.mkdir(exist_ok=True)
        else:
            workdir = Path(tempdir).absolute()

        force_recording = cast(str, args.force_recording)

        scraper = NewsScraper(workdir, source)

        if force_recording:
            scraper.recording_file = force_recording
            scraper.process_recording()
            sys.exit(0)

        server = NewsServer(scraper, http_addr)

        scraper.start()
        server.start()

        while True:
            time.sleep(1)


if __name__ == '__main__':
    main()
