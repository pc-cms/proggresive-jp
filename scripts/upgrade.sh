#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
./scripts/backup.sh
./scripts/prepare-wheels.sh
docker compose build app
docker compose up -d --wait
# Volumes retained. NEVER use docker compose down -v.
