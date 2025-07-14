#!/bin/bash
# captn CLI auto-completion script for Docker environments
# This script is designed to work inside Docker containers

_captn_complete() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # echo "DEBUG: _captn_complete called, cur='$cur', prev='$prev'" >&2

    # Basic command options
    opts="--version --force --run --dry-run --filter --log-level --help -v -f -r -t -l -h"

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

    # Default completion for other arguments
    if [[ ${cur} == * ]] ; then
        COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
        return 0
    fi
}

# Register the completion function for captn command
complete -F _captn_complete -o nospace captn

# Also register for python -m app (useful in development)
complete -F _captn_complete -o default -o nospace python

# Register for the full module path
complete -F _captn_complete -o default -o nospace -W "-m" python
complete -F _captn_complete -o default -o nospace -W "app" python