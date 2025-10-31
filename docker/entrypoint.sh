#!/bin/bash

echo "[ENTRYPOINT] captn version: ${VERSION}"
echo "[ENTRYPOINT] Preparing container environment..."

# Create necessary directories
mkdir -p /app/{conf,logs}

# Enable auto-completion for interactive shells
if [ -f /etc/bash_completion.d/captn ]; then
    echo "[ENTRYPOINT] Auto-completion script found and will be available in interactive shells"
    source /etc/bash_completion.d/captn
fi

# Check if arguments are provided
if [ $# -eq 0 ]; then
    # No arguments provided, start daemon mode
    echo "[ENTRYPOINT] Starting captn daemon with scheduler..."
    exec captn --daemon
else
    # Arguments provided, execute the command directly
    echo "[ENTRYPOINT] Executing command: $@"
    exec captn "$@"
fi
