#!/bin/bash
LOCKFILE="/tmp/captn.lock"
TIMEOUT=18000 # 5 hours in seconds

# Function to print log with timestamp and log level
log() {
  local level="$1"
  shift
  printf "%s %-7s %s\n" "$(date '+%Y-%m-%d %H:%M:%S.%3N')" "$level" "$*"
}

# Open file descriptor for locking
exec 200>"$LOCKFILE"

# Try to acquire lock
flock -n 200 || { log "ERROR" "Another instance is running."; exit 1; }

# Setup environment
mkdir -p /app/{conf,logs}

log "INFO" "Starting captn.io/captn"

# Trap to ensure lock is released on exit
trap 'rm -f "$LOCKFILE"; exit' INT TERM EXIT

# Change directory, activate the python virtual environment and execute the script with timeout
cd / || exit 1
if [ ! -f /opt/venv/bin/activate ]; then
  log "ERROR" "Virtual environment not found at /opt/venv. Exiting."
  exit 1
fi

. /opt/venv/bin/activate
timeout $TIMEOUT python -u -m app "$@"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 124 ]; then
  log "ERROR" "Execution timed out after $TIMEOUT seconds (args: $*)."
fi

log "INFO" "Finished with exit code $EXIT_CODE"

# Release lock and remove lockfile manually
rm -f "$LOCKFILE"

# Remove trap before exiting to avoid unnecessary deletion attempts
trap - INT TERM EXIT

exit $EXIT_CODE
