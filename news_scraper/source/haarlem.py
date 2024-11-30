from collections.abc import Iterator
from typing import override

from news_scraper.source import NewsSource, Segment, find_offset


class RadioHaarlemNewsSource(NewsSource):
    def __init__(self):
        super().__init__(record_url = 'http://live.radiohaarlem.nl:8000/radio.mp3')

    @override
    def segments(self, recording_file: str) -> Iterator[Segment]:
        start = find_offset(recording_file, 'fragments/haarlem_start.wav')
        end = find_offset(recording_file, 'fragments/haarlem_eind.wav')
        if start and end:
            yield Segment(start, end - 1.8)
