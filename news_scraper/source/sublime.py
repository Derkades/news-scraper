from collections.abc import Iterator
from typing import override

from news_scraper.source import NewsSource, Segment, find_offset


class SublimeNewsSource(NewsSource):
    def __init__(self):
        super().__init__(
            record_url="https://playerservices.streamtheworld.com/api/livestream-redirect/SUBLIME.mp3"
        )

    @override
    def segments(self, recording_file: str) -> Iterator[Segment]:
        # Voorbeeld werkdag overdag tijdens spits: reclame - start - weer - verkeer - eind_reclame - reclame
        # Voorbeeld werkdag avond                : (reclame -) start - weer - eind_nacht
        # na "eind speciaal" volgt normaal gesproken iets als "sublime weekend" of "candy's world", maar heet eerste stukje lijkt altijd hetzelfde

        nieuws_start = find_offset(recording_file, "fragments/sublime_nieuws2.wav")
        if not nieuws_start:
            return
        weer_start = find_offset(
            recording_file, "fragments/sublime_weer2.wav", search_from=nieuws_start
        )

        # Nieuws is altijd hetzelfde, van "En nu het nieuws" tot "Sublime weer"
        if nieuws_start and weer_start:
            yield Segment(nieuws_start - 0.95, weer_start - 1.7)

        # deuntjes zijn veranderd, nu kan alleen nog het nieuws betrouwbaar geknipt worden

        # if weer_start:
        #     # Tijdens de spits is er verkeersinformatie, dan gaat het weer tot het verkeer deuntje
        #     # verkeer3 sample is te kort
        #     verkeer_start = find_offset(recording_file, 'fragments/sublime_verkeer3.wav', search_from=weer_start)
        #     if verkeer_start:
        #         yield Segment(weer_start, verkeer_start - 0.3)
        #         return

        #     # anders gaat weer tot het eind, maar welk eind?

        #     # eind_reclame speelt soms ook voor het nieuws, dus zoek specifiek na het weer
        #     eind_reclame = find_offset(recording_file, 'fragments/sublime_eind_reclame.wav', search_from=weer_start)
        #     if eind_reclame:
        #         yield Segment(weer_start + 0.05, eind_reclame - 1.35)
        #         return

        #     eind_funky = find_offset(recording_file, 'fragments/sublime_eind_funky_friday.wav', search_from=weer_start)
        #     if eind_funky:
        #         yield Segment(weer_start + 0.05, eind_funky - 4.85)
        #         return

        #     eind_speciaal = find_offset(recording_file, 'fragments/sublime_eind_speciaal.wav', search_from=weer_start)
        #     if eind_speciaal:
        #         yield Segment(weer_start + 0.05, eind_speciaal - 3.5)
        #         return

        #     # hogere kans op verkeerde detectie dus wordt als laatste geprobeerd
        #     eind_nacht = find_offset(recording_file, 'fragments/sublime_eind_nacht.wav', search_from=weer_start)
        #     if eind_nacht:
        #         yield Segment(weer_start + 0.05, eind_nacht - 5.3)
        #         return

        # Eind is ook soms anders, dan maar geen weer. In ieder geval hebben we het nieuws.
