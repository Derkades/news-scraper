# News scraper

Scrapes news bulletins from various sources to be used in hobby projects.

## Requirements

 * numpy
 * scipy
 * ffmpeg

## Usage

```
git clone https://github.com/Derkades/news-scraper
cd news-scraper
python3 -m news_scraper --source <source>
```

## News sources

 * Radio Haarlem
 * Kink (Recommended)
 * NPO Radio 2
 * ~~Sublime (Broken)~~

## API Usage

News can be downloaded by making a GET request to `/news.wav`. It is returned in mono wave PCM format. If no news recording is available, a 503 status code is returned.

## Development

To debug a specific recording, obtain it from /tmp. For example: `/tmp/news-scraper-__adqoey/recording.wav`. Or manually create a recording using `ffmpeg -i https://... -ac 1 -channel_layout mono recording.wav`.

If you are using docker, you can do this using `docker exec news ls /tmp` to find the directory name, followed by `docker cp news:/tmp/news-scraper-__adqoey .`

You can now run the news scraper on this specific recording: `python3 -m news_scraper --source ... --force-recording recording.wav --persistent`.

The `--persistent` flag causes the program to place the resulting news audio in `./data` instead of in temporary storage.
