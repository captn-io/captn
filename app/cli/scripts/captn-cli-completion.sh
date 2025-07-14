#!/bin/bash
# captn CLI auto-completion script for Docker environments
# This script is designed to work inside Docker containers

_captn_complete() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # echo "DEBUG: _captn_complete called, cur='$cur', prev='$prev'" >&2

    # Check if we're completing the first argument (after the command)
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        # First argument - show main options
        opts="--help --version --dry-run --run --filter --log-level --clear-logs --force -h -v -t -r -f -l -c"
        COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
        return 0
    fi

    # Check if we already have certain flags to avoid suggesting them again
    local used_flags=()
    for ((i=1; i<COMP_CWORD; i++)); do
        case "${COMP_WORDS[i]}" in
            --help|-h|--version|-v)
                # These are standalone flags, don't suggest them again
                used_flags+=("${COMP_WORDS[i]}")
                ;;
            --dry-run|-t|--run|-r)
                # These are mutually exclusive, don't suggest the other
                used_flags+=("--dry-run" "--run" "-t" "-r")
                ;;
            --force|-f)
                used_flags+=("--force" "-f")
                ;;
            --clear-logs|-c)
                used_flags+=("--clear-logs" "-c")
                ;;
        esac
    done

    # Handle --filter argument completion
    if [[ ${prev} == "--filter" ]] || [[ ${prev} == "-f" ]]; then
        COMPREPLY=($(compgen -W "name= status=" -- "${cur}"))
        return 0
    fi

    # Handle --log-level argument completion
    if [[ ${prev} == "--log-level" ]] || [[ ${prev} == "-l" ]]; then
        local levels="debug info warning error critical"
        COMPREPLY=($(compgen -W "${levels}" -- "${cur}"))
        return 0
    fi

    # Build available options excluding already used ones
    opts="--help --version --dry-run --run --filter --log-level --clear-logs --force -h -v -t -r -f -l -c"

    # Remove used flags from suggestions
    for flag in "${used_flags[@]}"; do
        opts=$(echo "$opts" | sed "s/\b$flag\b//g")
    done

    # Filter options based on what user has typed
    if [[ ${cur} == -* ]]; then
        # User is typing a flag, show matching flags
        COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
    else
        # User might be typing a value, don't show flags
        COMPREPLY=()
    fi
}

# Register the completion function for captn command
complete -F _captn_complete -o nospace captn

# Also register for python -m app (useful in development)
complete -F _captn_complete -o default -o nospace python

# Register for the full module path
complete -F _captn_complete -o default -o nospace -W "-m" python
complete -F _captn_complete -o default -o nospace -W "app" python