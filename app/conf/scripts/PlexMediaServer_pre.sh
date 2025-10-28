#!/bin/bash
# Generic Pre-Update Script
# This script is executed before container updates

set -e

echo "=== Pre-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Log Level: $CAPTN_LOG_LEVEL"
echo "Config Dir: $CAPTN_CONFIG_DIR"
echo "Scripts Dir: $CAPTN_SCRIPTS_DIR"
echo "Timestamp: $(date)"


echo "Skipping backups because they take too long..."


echo "=== Pre-Update Script Completed ==="
exit 0