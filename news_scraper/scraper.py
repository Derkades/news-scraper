import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import override

from news_scraper.source import NewsSource

_LOGGER = logging.getLogger()

class NewsScraper(Thread):
    MAX_NEWS_AGE: int = 7200
    workdir: Path
    news_path: Path
    recording_file: str
    source: NewsSource
    last_activation: float

    def __init__(
        self,
        workdir: Path,
        source: NewsSource,
    ):
        super().__init__(daemon=True)
        self.workdir = workdir
        self.recording_file = f"{self.workdir}/recording.wav"
        self.news_path = Path(workdir, "news.wav")
        self.source = source
        self.last_activation = 0

    def record_stream(self):
        subprocess.check_call(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostdin",
                "-y",  # overwrite
                "-i",
                self.source.record_url,  # input file
                "-map",
                "0:a",  # only keep audio
                "-map_metadata",
                "-1",  # discard metadata
                "-ac",
                "1",  # downmix to mono, saves space and source is mono anyway
                "-channel_layout",
                "mono",
                "-t",
                str(self.source.record_duration),  # max duration
                self.recording_file,
            ],  # output file
            shell=False,
        )
        _LOGGER.info("finished recording")

    def process_recording(self):
        _LOGGER.info("finding segments")
        segment_files: list[Path] = []

        for i, segment in enumerate(self.source.segments(self.recording_file)):
            _LOGGER.info("extracting audio %s %s", i, segment)
            segment_file = Path(self.workdir, f"segment{i}.wav")
            subprocess.check_call(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-y",
                    "-i",
                    self.recording_file,
                    "-ss",
                    str(segment.start),
                    "-t",
                    str(segment.end - segment.start),
                    segment_file.as_posix(),
                ],
                shell=False,
            )
            segment_files.append(segment_file)

        if not segment_files:
            _LOGGER.error('no segments found')
            return

        _LOGGER.info("joining segments")
        list_file = Path(self.workdir, "list.txt")
        list_file.write_text(
            "\n".join([f"file '{file.as_posix()}'" for file in segment_files]),
            encoding="utf-8",
        )

        subprocess.check_call(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostdin",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file.as_posix(),
                "-c",
                "copy",
                self.news_path.as_posix(),
            ],
            shell=False,
        )

        list_file.unlink()
        for segment_file in segment_files:
            segment_file.unlink()

    @override
    def run(self):
        _LOGGER.info('scraping thread started')

        while True:
            if datetime.now().minute != self.source.record_start_minute:
                time.sleep(30)
                continue

            _LOGGER.info("recording time!")

            try:
                self.record_stream()
                self.process_recording()
            except Exception:
                _LOGGER.warning("failed to scrape news", exc_info=True)
                time.sleep(10)

    def get_news(self) -> bytes | None:
        if not self.news_path.exists():
            return None

        if self.news_path.stat().st_mtime < time.time() - self.MAX_NEWS_AGE:
            return None

        return self.news_path.read_bytes()
