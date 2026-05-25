#!/bin/bash

set -e

echo "Waiting for Nextcloud to be INSTALLED..."
until php /var/www/html/occ status 2>/dev/null | grep -q "installed: true"; do sleep 2; done

echo "Configuring ONLYOFFICE via occ..."

php /var/www/html/occ app:install onlyoffice || php /var/www/html/occ app:enable onlyoffice

php /var/www/html/occ config:app:set onlyoffice DocumentServerUrl --value="/ds-vpath/"
php /var/www/html/occ config:app:set onlyoffice DocumentServerInternalUrl --value="http://onlyoffice-document-server/"
php /var/www/html/occ config:app:set onlyoffice StorageUrl --value="http://nginx-server/"
php /var/www/html/occ config:app:set onlyoffice jwt_secret --value="${JWT_SECRET}"
php /var/www/html/occ config:app:set onlyoffice customizationForcesave --value=true

# callback URL для server-side (DS external links) идёт через docker-network
# hostname. overwriteprotocol/overwritehost НЕ ставим - петля на /login.
php /var/www/html/occ config:system:set overwrite.cli.url --value="http://nginx-server" --type=string

php /var/www/html/occ config:system:set trusted_proxies --value="${NEXTCLOUD_TRUSTED_PROXIES}" --type=json
php /var/www/html/occ config:system:set trusted_domains 0 --value="nginx-server" --type=string
php /var/www/html/occ config:system:set trusted_domains 1 --value="${NEXTCLOUD_HOST}" --type=string

php /var/www/html/occ config:system:set memcache.local --value="\\OC\\Memcache\\APCu" --type=string
php /var/www/html/occ background:cron

php /var/www/html/occ app:install forms || php /var/www/html/occ app:enable forms

php /var/www/html/occ config:system:set appstoreenabled --value=false --type=boolean
php /var/www/html/occ config:system:set has_internet_connection --value=false --type=boolean

php /var/www/html/occ maintenance:repair --include-expensive
php /var/www/html/occ db:add-missing-indices

echo "ONLYOFFICE and Forms integration apps configured OK"
