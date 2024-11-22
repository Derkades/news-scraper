import math
import subprocess
import sys
import tempfile
import time
import traceback
import wave
from abc import ABC, abstractmethod
from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import Iterator
from wave import Wave_read

import numpy as np
from scipy.signal import correlate


# https://stackoverflow.com/a/62298670/4833737
def read_wav(file_name):
    """
    Read wave file as float array normalized -1.0 to 1.0
    """
    # Read file to get buffer
    ifile: Wave_read = wave.open(file_name)
    samples = ifile.getnframes()
    audio = ifile.readframes(samples)

    # Convert buffer to float32 using NumPy
    audio_as_np_int16 = np.frombuffer(audio, dtype=np.int16)
    audio_as_np_float32 = audio_as_np_int16.astype(np.float32)

    # Normalise float32 array so that values are between -1.0 and +1.0
    return audio_as_np_float32 / 2**15, ifile.getframerate()


def find_offset(within_file, find_file, search_from = 0.0) -> float | None:
    y_within, sr_within = read_wav(within_file)
    y_find, _sr_find = read_wav(find_file)
    y_within = y_within[int(search_from*sr_within):]
    c = correlate(y_within, y_find)
    peak = np.argmax(c)
    offset = round(peak / sr_within, 2) + search_from
    confidence = (c[peak] / len(y_find)) * 100
    print(f'found {find_file} at {offset}s {math.floor(offset / 60)}:{round(offset % 60)} with confidence {confidence}')
    if confidence < 0.8:
        return None
    return float(offset)


@dataclass
class Segment:
    start: float
    end: float


class NewsProvider(ABC):
    record_url: str
    record_start_minute = 57
    record_duration = 9*60

    @abstractmethod
    def segments(self, recording_file: str) -> Iterator[Segment]:
        pass


class SublimeNewsProvider(NewsProvider):
    record_url = 'https://playerservices.streamtheworld.com/api/livestream-redirect/SUBLIME.mp3'

    def segments(self, recording_file: str) -> Iterator[Segment]:
        # Voorbeeld werkdag overdag tijdens spits: reclame - start - weer - verkeer - eind_reclame - reclame
        # Voorbeeld werkdag avond                : (reclame -) start - weer - eind_nacht
        # na "eind speciaal" volgt normaal gesproken iets als "sublime weekend" of "candy's world", maar heet eerste stukje lijkt altijd hetzelfde

        nieuws_start = find_offset(recording_file, 'fragments/sublime_nieuws2.wav')
        if not nieuws_start:
            return
        weer_start = find_offset(recording_file, 'fragments/sublime_weer2.wav', search_from=nieuws_start)

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


class NpoRadio2NewsProvider(NewsProvider):
    record_url = 'https://icecast.omroep.nl/radio2-bb-mp3'

    def segments(self, recording_file: str) -> Iterator[Segment]:
        nieuws_start = find_offset(recording_file, 'fragments/npo_radio2_nieuws.wav')
        if nieuws_start:
            weer_start = find_offset(recording_file, 'fragments/npo_radio2_weer.wav', search_from=nieuws_start)
            if weer_start:
                # nieuws einde is elke keer anders, dus we kunnen alleen maar tot het weer
                yield Segment(nieuws_start + 0.1, weer_start - 0.07)


NEWS_PROVIDERS = {'sublime': SublimeNewsProvider(),
                  'npo-radio2': NpoRadio2NewsProvider()}


class NewsScraper:
    MAX_NEWS_AGE = 7200
    workdir: Path
    news_path: Path
    recording_file: str
    provider: NewsProvider
    http_addr: tuple[str, int]
    last_activation: float

    def __init__(self,
                 workdir: Path,
                 provider: NewsProvider,
                 http_addr: tuple[str, int],
                 force_recording: str):
        self.workdir = workdir
        self.recording_file = f'{self.workdir}/recording.wav'
        self.news_path = Path(workdir, 'news.wav')
        self.provider = provider
        self.http_addr = http_addr
        self.force_recording = force_recording
        self.last_activation = 0

        if force_recording:
            self.recording_file = force_recording
            self.scrape_process()
            sys.exit(0)

        Thread(target=self.scrape_thread, daemon=True).start()
        Thread(target=self.http_thread, daemon=True).start()

        while True:
            time.sleep(1)


    def scrape_record(self):
        subprocess.check_call(['ffmpeg',
                                '-hide_banner',
                                '-nostdin',
                                '-y', # overwrite
                                '-i', self.provider.record_url, # input file
                                '-map', '0:a', # only keep audio
                                '-map_metadata', '-1',  # discard metadata
                                '-ac', '1', # downmix to mono, saves space and source is mono anyway
                                '-channel_layout', 'mono',
                                '-t', str(self.provider.record_duration), # max duration
                                self.recording_file], # output file
                                shell=False)
        print('finished recording')


    def scrape_process(self):
        print('finding segments')
        segment_files: list[Path] = []

        for i, segment in enumerate(self.provider.segments(self.recording_file)):
            print('extracting audio', i, segment)
            segment_file = Path(self.workdir, f'segment{i}.wav')
            # subprocess.check_call(['sox', recording_file, segment_file, 'trim', str(segment.start), f'={segment.end}'], shell=False)
            subprocess.check_call(['ffmpeg',
                                    '-nostdin',
                                    '-hide_banner',
                                    '-y',
                                    '-i', self.recording_file,
                                    '-ss', str(segment.start),
                                    '-t', str(segment.end - segment.start),
                                    segment_file.as_posix()],
                                    shell=False)
            segment_files.append(segment_file)

        if not segment_files:
            print('ERROR: no segments found')
            return

        print('joining segments')
        list_file = Path(self.workdir, 'list.txt')
        list_file.write_text('\n'.join([f"file '{file.as_posix()}'" for file in segment_files]), encoding='utf-8')

        subprocess.check_call(['ffmpeg',
                                '-hide_banner',
                                '-nostdin',
                                '-y',
                                '-f', 'concat',
                                '-safe', '0',
                                '-i', list_file.as_posix(),
                                '-c', 'copy',
                                self.news_path.as_posix()],
                                shell=False)

        list_file.unlink()
        for segment_file in segment_files:
            segment_file.unlink()


    def scrape_thread(self):
        print('scraping thread started')

        while True:
            # TODO implement activation system in music player
            # if self.last_activation < time.time() - 600:
            #     print('not active')
            #     time.sleep(60)
            #     continue

            if datetime.now().minute != self.provider.record_start_minute:
                time.sleep(30)
                continue

            print('recording time!')

            try:
                self.scrape_record()
                self.scrape_process()
            except Exception:
                traceback.print_exc()
                time.sleep(10)

    def http_thread(outer_self):
        class HTTPHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != '/news.wav':
                    self.send_response(404) # Not Found
                    self.end_headers()
                    return

                if not outer_self.news_path.exists():
                    self.send_response(503) # Service Unavailable
                    self.end_headers()
                    self.wfile.write(b'news missing\n')
                    return

                if outer_self.news_path.stat().st_mtime < time.time() - outer_self.MAX_NEWS_AGE:
                    self.send_response(503) # Service Unavailable
                    self.end_headers()
                    self.wfile.write(b'news outdated\n')
                    return

                self.send_response(200) # OK
                self.send_header('Content-Type', 'audio/wav')
                self.send_header('Content-Disposition', 'attachment; filename="news.wav"')
                self.send_header('Content-Length', outer_self.news_path.stat().st_size)
                self.end_headers()
                self.wfile.write(outer_self.news_path.read_bytes())

            def do_POST(self):
                if self.path != '/activate':
                    self.send_response(404) # Not Found
                    self.end_headers()
                    return

                self.send_response(204) # No Content
                self.end_headers()
                outer_self.last_activation = time.time()

        server = HTTPServer(outer_self.http_addr, HTTPHandler)
        server.serve_forever()


def main():
    parser = ArgumentParser()

    parser.add_argument('--provider', type=str, required=True,
                        help='News provider. Choose from: ' + ','.join(NEWS_PROVIDERS.keys()))
    parser.add_argument('--http-bind', type=str, default='127.0.0.1')
    parser.add_argument('--http-port', type=int, default=43473)

    parser_dev = parser.add_argument_group('development options')
    parser_dev.add_argument('--persistent', action='store_true',
                        help='Store temporary data in persistent ./data instead of in /tmp')
    parser_dev.add_argument('--force-recording', type=str,
                        help='Path to an existing recording. This recording will be processed, then the program will exit immediately')

    args = parser.parse_args()

    provider = NEWS_PROVIDERS[args.provider]
    http_addr = (args.http_bind, args.http_port)

    with tempfile.TemporaryDirectory(prefix='news-scraper-') as tempdir:
        if args.persistent:
            # TODO configurable with --persistent value
            workdir = Path('./data').absolute()
            workdir.mkdir(exist_ok=True)
        else:
            workdir = Path(tempdir).absolute()

        NewsScraper(workdir, provider, http_addr, args.force_recording)


if __name__ == '__main__':
    main()
