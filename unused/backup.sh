#!/bin/bash

DB_NAME="heist"
BACKUP_DIR="/heist/unused"
TIMESTAMP=$(date +'%Y%m%d_%H%M%S')
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}.sql"

mkdir -p "$BACKUP_DIR"

PGPASSWORD="cosmingyatrizz44" pg_dump -U postgres -h localhost "$DB_NAME" > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "Backup successful: $BACKUP_FILE"
else
    echo "Backup failed!"
    exit 1
fi
