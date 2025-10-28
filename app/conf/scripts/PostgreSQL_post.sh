#!/bin/bash
# PostgreSQL-specific Post-Update Script
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

if [ "$CAPTN_DRY_RUN" = "false" ]; then
    if docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
        echo "Container $CAPTN_CONTAINER_NAME is running, proceeding..."
    else
        echo "Container $CAPTN_CONTAINER_NAME is not running. Exiting."
        exit 1
    fi

    # Execute SQL to list all database names
    DB_NAMES=$(docker exec -i "$CAPTN_CONTAINER_NAME" psql -U root -t -c "SELECT datname FROM pg_database WHERE datistemplate = false AND datname NOT IN ('postgres', 'root');")

    # Unpause corresponding containers to each database
    echo "Unpausing corresponding containers to each database..."
    for db_name in $DB_NAMES; do
        # Check if corresponding container exists and is running
        if docker ps --format "{{.Names}}" | grep -q "^${db_name}$"; then
            echo "Unpausing container $db_name..."
            docker unpause $db_name
        else
            # Search for Containers beginning with the database name
            CONTAINER_NAMES=$(docker ps --format "{{.Names}}" | grep "^${db_name}-")
            if [ -n "$CONTAINER_NAMES" ]; then
                for CONTAINER_NAME in $CONTAINER_NAMES; do
                    echo "Unpausing container $CONTAINER_NAME..."
                    docker unpause $CONTAINER_NAME
                done
            else
                echo "No container found for database $db_name. Exiting."
            fi
        fi
    done
else
    echo "Would process post-update tasks"
fi

echo "=== Post-Update Script Completed ==="
exit 0