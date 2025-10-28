#!/bin/bash
# pgAdmin-specific Post-Update Script
# This script is executed after container updates

set -e

echo "=== Post-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Log Level: $CAPTN_LOG_LEVEL"
echo "Config Dir: $CAPTN_CONFIG_DIR"
echo "Scripts Dir: $CAPTN_SCRIPTS_DIR"
echo "Timestamp: $(date)"

echo "Resuming immich-server..."
docker unpause immich-server

echo "=== Post-Update Script Completed ==="
exit 0