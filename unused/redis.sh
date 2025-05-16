#!/bin/bash

sudo apt update
sudo apt install -y redis-server

sudo systemctl enable redis-server

sudo systemctl start redis-server

REDIS_CONF_DIR="/etc/redis"
REDIS_DATA_DIR="/var/lib/redis6380"
REDIS_CONF_FILE="${REDIS_CONF_DIR}/redis6380.conf"

sudo mkdir -p "$REDIS_DATA_DIR"
sudo cp "${REDIS_CONF_DIR}/redis.conf" "$REDIS_CONF_FILE"

sudo sed -i "s/^port .*/port 6380/" "$REDIS_CONF_FILE"
sudo sed -i "s|^dir .*|dir $REDIS_DATA_DIR|" "$REDIS_CONF_FILE"
sudo sed -i "s/^# save/save/" "$REDIS_CONF_FILE"

sudo tee /etc/systemd/system/redis6380.service > /dev/null <<EOL
[Unit]
Description=Redis instance on port 6380
After=network.target

[Service]
ExecStart=/usr/bin/redis-server $REDIS_CONF_FILE
ExecStop=/usr/bin/redis-cli -p 6380 shutdown
Restart=always
User=redis
Group=redis

[Install]
WantedBy=multi-user.target
EOL

sudo systemctl daemon-reload
sudo systemctl enable redis6380
sudo systemctl start redis6380

if systemctl is-active --quiet redis6380; then
    echo "Second Redis instance started on port 6380 with persistence enabled."
else
    echo "Failed to start the second Redis instance!"
    exit 1
fi
