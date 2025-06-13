from collections.abc import Iterator
from typing import override
from news_scraper.source import NewsSource, Segment, find_offset


class KinkNewsSource(NewsSource):
    def __init__(self):
        super().__init__(
            'ANP Nieuws',
            record_url="https://playerservices.streamtheworld.com/api/livestream-redirect/KINK.mp3"
        )

    @override
    def segments(self, recording_file: str) -> Iterator[Segment]:
        nieuws_start = find_offset(recording_file, "fragments/kink_nieuws.wav")
        if nieuws_start:
            nieuws_eind = find_offset(
                recording_file,
                "fragments/kink_nieuws_eind.wav",
                search_from=nieuws_start,
            )
            if nieuws_eind:
                # nieuws einde is elke keer anders, dus we kunnen alleen maar tot het weer
                yield Segment(nieuws_start, nieuws_eind - 1.77)
