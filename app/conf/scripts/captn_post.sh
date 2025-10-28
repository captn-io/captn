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

echo "Updating apk..."
apk update

echo "Installing screen..."
apk add screen

echo "Installing openssh..."
apk add openssh

echo "Installing git..."
apk add git

echo "Installing bind-tools..."
apk add bind-tools

echo "Installing jq..."
apk add jq

echo "=== Pre-Update Script Completed ==="
exit 0