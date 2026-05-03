#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f .env ]]; then
  echo "Error: .env not found in $SCRIPT_DIR" >&2
  exit 1
fi

set -a
source <(sed 's/\r$//' .env)
set +a

WINDMILL_HOST="${WINDMILL_HOST:-${NEXTCLOUD_HOST:-localhost}}"
WINDMILL_PORT="${WINDMILL_PORT:-8000}"
WM_REDIRECT_URI="http://${WINDMILL_HOST}:${WINDMILL_PORT}/workspace_settings?tab=native_triggers&service=nextcloud"

echo "Using redirect URI: ${WM_REDIRECT_URI}" >&2

docker compose exec -u www-data -T -e WM_REDIRECT_URI="$WM_REDIRECT_URI" app sh -lc 'cat > /tmp/wm_oauth_create.php << "PHP"
<?php
declare(strict_types=1);

require_once "/var/www/html/lib/base.php";

$server = \OC::$server;
$secureRandom = $server->get(\OCP\Security\ISecureRandom::class);
$crypto = $server->get(\OCP\Security\ICrypto::class);
$clientMapper = $server->get(\OCA\OAuth2\Db\ClientMapper::class);

$chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
$clientId = $secureRandom->generate(64, $chars);
$plainSecret = $secureRandom->generate(64, $chars);
$hashedSecret = bin2hex($crypto->calculateHMAC($plainSecret));

$client = new \OCA\OAuth2\Db\Client();
$client->setName("Windmill");
$client->setRedirectUri(getenv("WM_REDIRECT_URI") ?: "http://windmill.local:8000/workspace_settings?tab=native_triggers&service=nextcloud");
$client->setClientIdentifier($clientId);
$client->setSecret($hashedSecret);

$client = $clientMapper->insert($client);

echo "CLIENT_ID=" . $clientId . PHP_EOL;
echo "CLIENT_SECRET=" . $plainSecret . PHP_EOL;
PHP
php /tmp/wm_oauth_create.php'