#!/bin/bash
# Nextcloud-specific Pre-Update Script
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

    echo "Turning on Maintenance Mode for $CAPTN_CONTAINER_NAME..."
    docker exec -u 33 $CAPTN_CONTAINER_NAME php console.php maintenance:mode --on

    # Check if maintenance mode is on by polling the URL
    URL="https://cloud.jk-net.com/"
    TIMEOUT=300   # max wait time in seconds
    INTERVAL=5    # interval between checks in seconds
    ELAPSED=0

    echo "Waiting for maintenance mode to be enabled..."

    while true; do
        # Use curl to check HTTP status code
        HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "$URL")

        # Typically maintenance mode returns 503 or similar, normal mode 200
        if [ "$HTTP_STATUS" -eq 503 ]; then
            echo "Maintenance mode is enabled"
            break
        fi

        # Timeout check
        if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
            echo "Timeout reached after $TIMEOUT seconds"
            exit 1
        fi

        sleep "$INTERVAL"
        ELAPSED=$((ELAPSED + INTERVAL))
    done
    
    # Execute backup script
    echo "Executing backup script \"/var/opt/JK.NET/data/scripts/${CAPTN_CONTAINER_NAME,,}.sh\" with parameter \"-b\""...
    "/var/opt/JK.NET/data/scripts/${CAPTN_CONTAINER_NAME,,}.sh" -b
else
    echo "Would create backup of container data"
fi

echo "=== Pre-Update Script Completed ==="
exit 0