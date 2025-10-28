#!/bin/bash
# pgAdmin-specific Post-Update Script
# This script is executed after container updates

set -e

CONTAINER_DATA_BASE_DIR="/var/opt/JK.NET/data/docker"

echo "=== Post-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Log Level: $CAPTN_LOG_LEVEL"
echo "Config Dir: $CAPTN_CONFIG_DIR"
echo "Scripts Dir: $CAPTN_SCRIPTS_DIR"
echo "Data Base Dir: $CONTAINER_DATA_BASE_DIR"
echo "Timestamp: $(date)"

echo "Changing ownership of appdata directory \"$CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata\" to 1000:1000..."
chown -Rf 1000:1000 "$CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata"

echo "=== Post-Update Script Completed ==="
exit 0