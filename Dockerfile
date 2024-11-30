FROM python:3.13-slim AS base

FROM base AS build-ffmpeg

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential wget bzip2 nasm pkg-config libssl-dev

RUN mkdir /build

RUN cd /build && \
    wget -O ffmpeg-snapshot.tar.bz2 https://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2 && \
    tar xjf ffmpeg-snapshot.tar.bz2

RUN cd /build/ffmpeg && \
    ./configure \
        --prefix="/build/ffmpeg" \
        --extra-cflags="-I/build/ffmpeg/include" \
        --extra-ldflags="-L/build/ffmpeg/lib" \
        --extra-libs="-lm" \
        --ld="g++" \
        # Configuration options
        --disable-autodetect \
        # Enable HTTPS support
        --enable-openssl \
        # Program options
        --disable-ffplay \
        --disable-ffprobe \
        # Documentation options
        --disable-doc \
        # Component options
        --disable-avdevice \
        # Individual component options
        --disable-everything \
        --enable-protocol=file \
        --enable-protocol=http \
        --enable-protocol=https \
        --enable-decoder=mp3 \
        --enable-decoder=pcm_s16le \
        --enable-demuxer=mp3 \
        --enable-demuxer=wav \
        --enable-demuxer=concat \
        --enable-encoder=pcm_s16le \
        --enable-muxer=wav \
        --enable-filter=aresample \
        --enable-filter=concat \
        && \
    make -j8

FROM base AS runtime

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

COPY --from=build-ffmpeg /build/ffmpeg/ffmpeg /usr/local/bin/

RUN mkdir /app
WORKDIR /app

COPY news_scraper ./news_scraper
COPY fragments ./fragments

ENV PYTHONUNBUFFERED=1

STOPSIGNAL SIGINT

ENTRYPOINT ["python3", "-m", "news_scraper"]
