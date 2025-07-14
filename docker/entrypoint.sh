#!/bin/bash

echo "[ENTRYPOINT] captn version: ${VERSION}"
echo "[ENTRYPOINT] Preparing container environment..."

# Set default cron schedule if not provided
if [ -z "${CRON_SCHEDULE}" ]; then
    export CRON_SCHEDULE="0 2 * * *"  # Default: Daily at 2 AM
    echo "[ENTRYPOINT] No CRON_SCHEDULE provided. Using default: ${CRON_SCHEDULE}"
else
    echo "[ENTRYPOINT] Using provided CRON_SCHEDULE: ${CRON_SCHEDULE}"
fi

# Create necessary directories
mkdir -p /app/{conf,logs}

# Enable auto-completion for interactive shells
if [ -f /etc/bash_completion.d/captn ]; then
    echo "[ENTRYPOINT] Auto-completion script found and will be available in interactive shells"
    source /etc/bash_completion.d/captn
fi

# Check if configuration file exists
if [ ! -f "/app/conf/captn.cfg" ]; then
    echo "[ENTRYPOINT] Configuration file not found. Creating default configuration..."
    cat > /app/conf/captn.cfg << 'EOF'
[general]
dryRun = false

[logging]
level = INFO
EOF
fi

# Export all current environment variables except no_proxy to a temporary file
printenv | grep -v "no_proxy" > /tmp/container_env.sh

# Replace environment variable placeholders in crontab template
envsubst < /app/crontab.template > /tmp/crontab.body

# Merge exported environment variables and cronjob definition into a final crontab file
cat /tmp/container_env.sh /tmp/crontab.body > /tmp/crontab.final

# Install the new crontab from the final file
crontab /tmp/crontab.final

# Clean up temporary files
rm -f /tmp/container_env.sh
rm -f /tmp/crontab.body
rm -f /tmp/crontab.final

echo "[ENTRYPOINT] Starting cron daemon..."
cron -f
