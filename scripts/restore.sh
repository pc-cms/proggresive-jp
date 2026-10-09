#!/bin/sh
set -eu
# Restore ONLY to a new empty database; never overwrite a running casino.
[ "$#" -eq 2 ] || { echo 'Usage: restore.sh backups/file.dump progressive_restore_NAME'; exit 2; }
archive="$1"
target="$2"
case "$target" in progressive_restore_[a-zA-Z0-9_]*) ;; *) echo 'Use a new progressive_restore_NAME database'; exit 2 ;; esac
case "$target" in *[!a-zA-Z0-9_]*) exit 2 ;; esac
sha256sum -c "$archive.sha256"
docker compose exec -T db createdb -U progressive "$target"
docker compose exec -T db pg_restore -U progressive -d "$target" --exit-on-error < "$archive"
printf 'Restored into %s. Verify journal/reconciliation before switching DATABASE_URL.\n' "$target"
