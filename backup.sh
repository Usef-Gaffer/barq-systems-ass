#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_DIR}/barq_tasks_${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

docker compose exec -T postgres pg_dump -U barq_app -d barq_tasks -F c -f /tmp/backup.dump
docker compose cp postgres:/tmp/backup.dump "$BACKUP_FILE"
docker compose exec -T postgres rm -f /tmp/backup.dump

if [ ! -s "$BACKUP_FILE" ]; then
    echo "FAIL: backup file is missing or empty: $BACKUP_FILE" >&2
    exit 1
fi

echo "OK: backup created at $BACKUP_FILE ($(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE") bytes)"