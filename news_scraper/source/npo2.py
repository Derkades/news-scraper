from collections.abc import Iterator
from typing import override

from news_scraper.source import NewsSource, Segment, find_offset


class NPO2NewsSource(NewsSource):
    def __init__(self):
        super().__init__(record_url = 'https://icecast.omroep.nl/radio2-bb-mp3')

    @override
    def segments(self, recording_file: str) -> Iterator[Segment]:
        nieuws_start = find_offset(recording_file, 'fragments/npo_radio2_nieuws.wav')
        if nieuws_start:
            weer_start = find_offset(recording_file, 'fragments/npo_radio2_weer.wav', search_from=nieuws_start)
            if weer_start:
                # nieuws einde is elke keer anders, dus we kunnen alleen maar tot het weer
                yield Segment(nieuws_start + 0.1, weer_start - 0.07)
