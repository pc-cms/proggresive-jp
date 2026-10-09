#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p backups
chmod 700 backups
output="backups/progressive-$(date -u +%Y%m%dT%H%M%SZ).dump"
umask 077
docker compose exec -T db pg_dump -U progressive -d progressive -Fc > "$output.partial"
mv "$output.partial" "$output"
sha256sum "$output" > "$output.sha256"
printf '%s\n' "$output"
