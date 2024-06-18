# News scraper

Scrapes news bulletins from various sources to be used in hobby projects.

## API Usage

News can be downloaded by making a GET request to `/news.wav`.

As long as news is needed, make a post request to `/activate` at least every 10 minutes. Otherwise, no news will be downloaded to save resources and energy.
