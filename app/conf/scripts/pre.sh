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

if [ "$CAPTN_DRY_RUN" = "false" ]; then
    if docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
        echo "Container $CAPTN_CONTAINER_NAME is running, proceeding with backup..."
    else
        echo "Container $CAPTN_CONTAINER_NAME is not running. Exiting."
        exit 1
    fi

    # Execute backup script
    echo "Executing backup script \"/var/opt/JK.NET/data/scripts/${CAPTN_CONTAINER_NAME,,}.sh\" with parameter \"-b\""...
    "/var/opt/JK.NET/data/scripts/${CAPTN_CONTAINER_NAME,,}.sh" -b
else
    echo "Would create backup of container data"
fi

echo "=== Pre-Update Script Completed ==="
exit 0