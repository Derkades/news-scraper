import math
import wave
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from wave import Wave_read

import numpy as np
from scipy.signal import correlate


# https://stackoverflow.com/a/62298670/4833737
def read_wav(file_name: str):
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


def find_offset(within_file: str, find_file: str, search_from: float = 0.0) -> float | None:
    y_within, sr_within = read_wav(within_file)
    y_find, _sr_find = read_wav(find_file)
    y_within = y_within[int(search_from*sr_within):]
    c = correlate(y_within, y_find)
    peak = np.argmax(c)
    offset = round(peak / sr_within, 2) + search_from
    confidence = float((c[peak] / len(y_find)) * 100)
    print(f'found {find_file} at {offset}s {math.floor(offset / 60)}:{round(offset % 60)} with confidence {confidence}')
    if confidence < 0.8:
        return None
    return float(offset)


@dataclass
class Segment:
    start: float
    end: float


class NewsSource(ABC):
    record_url: str
    record_start_minute: int
    record_duration: int

    def __init__(
        self,
        *,
        record_url: str,
        record_start_minute: int = 57,
        record_duration: int = 9 * 60,
    ):
        self.record_url = record_url
        self.record_start_minute = record_start_minute
        self.record_duration = record_duration

    @abstractmethod
    def segments(self, recording_file: str) -> Iterator[Segment]:
        pass
