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


def find_offset(within_file, find_file):
    y_within, sr_within = read_wav(within_file)
    y_find, _sr_find = read_wav(find_file)
    c = correlate(y_within, y_find)
    peak = np.argmax(c)
    offset = round(peak / sr_within, 2)
    print(f'found {find_file} at {offset} with confidence {c[peak]}')
    # seems to be >1000 for true positive >1000 and <300 for false positive
    if c[peak] < 500:
        return None
    return offset


@dataclass
class Segment:
    start: float
    end: float


class NewsProvider(ABC):
    record_url: str
    record_start_minute = 58
    record_duration = 6*60

    @abstractmethod
    def segments(self, recording_file: str) -> Iterator[Segment]:
        pass


class SublimeNewsProvider(NewsProvider):
    record_url = 'https://22723.live.streamtheworld.com/SUBLIME.mp3'

    def segments(self, recording_file: str) -> Iterator[Segment]:
        nieuws_start = find_offset(recording_file, 'fragments/sublime_nieuws.wav')
        weer_start = find_offset(recording_file, 'fragments/sublime_weer.wav')
        verkeer_start = find_offset(recording_file, 'fragments/sublime_verkeer.wav')
        eind = find_offset(recording_file, 'fragments/sublime_eind.wav')

        # Voorbeeld werkdag om 12 uur 's middags:
        # reclame - start - weer - verkeer - eind - reclame

        # Voorbeeld werkdag om 11 uur 's avonds:
        # reclame - start - weer - alternatief eind

        # Nieuws is altijd hetzelfde, van "En nu het nieuws" tot "Sublime weer"
        if nieuws_start and weer_start:
            yield Segment(nieuws_start - 1.52, weer_start - 1.2)

        if weer_start:
            # Tijdens de spits is er verkeersinformatie
            # Dan gaat weer tot "Sublime verkeer"
            if verkeer_start:
                yield Segment(weer_start + 0.05, verkeer_start - 3.23)
            elif eind:
                # anders gaat verkeer tot het eind
                yield Segment(weer_start + 0.05, eind)

        # Eind is ook soms anders, dan maar geen weer. In ieder geval hebben we het nieuws.

NEWS_PROVIDERS = {'sublime': SublimeNewsProvider()}


class NewsScraper:
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
                print('waiting to start recording')
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

                if outer_self.news_path.stat().st_mtime < time.time() - 3600:
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
