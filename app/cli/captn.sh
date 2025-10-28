#!/bin/bash
LOCKFILE="/tmp/captn.lock"
TIMEOUT=36000 # 10 hours in seconds

# Function to print log with timestamp and log level
log() {
  local level="$1"
  shift
  printf "%s %-7s %s\n" "$(date '+%Y-%m-%d %H:%M:%S.%3N')" "$level" "$*"
}

# Setup environment
mkdir -p /app/{conf,logs}

log "INFO" "Starting captn.io/captn"

# Change directory, activate the python virtual environment and execute the script with timeout
cd / || exit 1
if [ ! -f /opt/venv/bin/activate ]; then
  log "ERROR" "Virtual environment not found at /opt/venv. Exiting."
  exit 1
fi

. /opt/venv/bin/activate

# Check if this is daemon mode (--daemon flag)
if [[ "$*" == *"--daemon"* ]]; then
  # Daemon mode - no lock required
  log "INFO" "Running in daemon mode"
  python -u -m app "$@"
  EXIT_CODE=$?
else
  # Update execution mode - acquire lock
  log "INFO" "Running update execution - acquiring lock"

  # Open file descriptor for locking
  exec 200>"$LOCKFILE"

  # Try to acquire lock
  flock -n 200 || {
    log "ERROR" "Another update process is running. Lock file: $LOCKFILE"
    log "ERROR" "To remove the lock manually: rm -f $LOCKFILE"
    exit 1;
  }

  # Trap to ensure lock is released on exit
  trap 'rm -f "$LOCKFILE"; exit' INT TERM EXIT

  timeout $TIMEOUT python -u -m app "$@"
  EXIT_CODE=$?

  # Release lock and remove lockfile manually
  rm -f "$LOCKFILE"

  # Remove trap before exiting to avoid unnecessary deletion attempts
  trap - INT TERM EXIT
fi

if [ $EXIT_CODE -eq 124 ]; then
  log "ERROR" "Execution timed out after $TIMEOUT seconds (args: $*)."
fi

log "INFO" "Finished with exit code $EXIT_CODE"

exit $EXIT_CODE
