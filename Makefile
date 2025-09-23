.PHONY: deploy

deploy:
	podman build -t ghcr.io/derkades/news-scraper .
	podman push ghcr.io/derkades/news-scraper
