#!/usr/bin/env bash
# Dev-утилита: self-signed TLS cert для локальной проверки HTTPS-варианта Б.
# В production в deploy/certs/ кладётся реальный сертификат (см. раздел HTTPS в README.md).
set -euo pipefail

HOSTNAME="${1:-nextcloud.localhost}"
DAYS="${2:-365}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CERTS_DIR="$REPO_ROOT/deploy/certs"
mkdir -p "$CERTS_DIR"

openssl req -x509 -nodes -days "$DAYS" \
  -newkey rsa:2048 \
  -keyout "$CERTS_DIR/server.key" \
  -out "$CERTS_DIR/server.crt" \
  -subj "/CN=$HOSTNAME" \
  -addext "subjectAltName=DNS:$HOSTNAME,DNS:localhost,IP:127.0.0.1"

chmod 644 "$CERTS_DIR/server.crt"
chmod 600 "$CERTS_DIR/server.key"

echo "Self-signed certificate generated:"
echo "  $CERTS_DIR/server.crt"
echo "  $CERTS_DIR/server.key"
echo ""
echo "CN: $HOSTNAME"
echo "Valid: $DAYS days"
