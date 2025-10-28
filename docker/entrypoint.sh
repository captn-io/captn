#!/bin/bash

echo "[ENTRYPOINT] captn version: ${VERSION}"
echo "[ENTRYPOINT] Preparing container environment..."

# Create necessary directories
mkdir -p /app/{conf,logs}

# Create/update example config file if it doesn't exist or needs updating (Example will be created by the app)
# echo "[ENTRYPOINT] Ensuring example config file is up-to-date..."
# if [ -f /opt/venv/bin/activate ]; then
#     . /opt/venv/bin/activate
#     python -c "from app.utils.config import create_example_config; create_example_config()" 2>/dev/null || echo "[ENTRYPOINT] Warning: Could not create example config file"
# else
#     echo "[ENTRYPOINT] Warning: Virtual environment not found, skipping example config creation"
# fi

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
