#!/bin/bash

DB_NAME="heist"
DB_USER="postgres"
DB_PASSWORD="cosmingyatrizz44"
BACKUP_FILE="/heist/unused/heist.sql"

sudo apt update
sudo apt install -y postgresql postgresql-contrib

sudo systemctl start postgresql
sudo systemctl enable postgresql

sudo -u postgres psql -c "ALTER USER $DB_USER PASSWORD '$DB_PASSWORD';"

sudo -u postgres createdb "$DB_NAME"

PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -h localhost -d "$DB_NAME" -f "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "Database $DB_NAME restored successfully."
else
    echo "Failed to restore database!"
    exit 1
fi
