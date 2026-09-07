#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="${1:?Usage: ./restore.sh <path-to-backup.dump>}"

if [ ! -s "$BACKUP_FILE" ]; then
    echo "FAIL: backup file not found or empty: $BACKUP_FILE" >&2
    exit 1
fi

docker compose cp "$BACKUP_FILE" postgres:/tmp/restore.dump
docker compose exec -T postgres pg_restore -U barq_app -d barq_tasks --clean --if-exists /tmp/restore.dump
docker compose exec -T postgres rm -f /tmp/restore.dump

echo "OK: restore completed from $BACKUP_FILE"