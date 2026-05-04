FROM nextcloud:33.0-fpm

RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends jq \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
