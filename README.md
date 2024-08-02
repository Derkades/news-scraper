# News scraper

Scrapes news bulletins from various sources to be used in hobby projects.

## API Usage

News can be downloaded by making a GET request to `/news.wav`. It is returned in mono wave PCM format. If no news recording is available, a 503 status code is returned.
