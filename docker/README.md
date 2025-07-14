# Scripts Directory

This directory contains utility scripts for the captn project.

## captn-cli-completion.sh

Bash completion script for the captn CLI. Provides intelligent tab-completion for command line options and parameters.

### Features

- **Smart filtering**: Only shows relevant options based on context
- **Mutual exclusion**: Prevents suggesting conflicting options (e.g., --dry-run vs --run)
- **No duplicates**: Avoids suggesting already used flags
- **Context-aware**: Shows appropriate completions for different argument positions

### Usage

#### Manual Setup
```bash
# Source the completion script
source app/cli/scripts/captn-cli-completion.sh

# Or add to your .bashrc for permanent setup
echo "source $(pwd)/app/cli/scripts/captn-cli-completion.sh" >> ~/.bashrc
```

#### Docker Environment
The completion script is automatically installed in the Docker image at `/etc/bash_completion.d/captn` and is available when running interactive shells in the container.

### Examples

```bash
# First argument - shows all main options
captn <Tab>
→ --help --version --dry-run --run --filter --log-level --clear-logs --force

# After --filter - shows remaining options
captn --filter name=nginx <Tab>
→ --log-level --clear-logs --force

# After --dry-run - doesn't suggest --run
captn --dry-run <Tab>
→ --filter --log-level --clear-logs --force
```

### Installation

For system-wide installation (requires root):
```bash
sudo cp app/cli/scripts/captn-cli-completion.sh /etc/bash_completion.d/captn
```

For user-specific installation:
```bash
cp app/cli/scripts/captn-cli-completion.sh ~/.local/share/bash-completion/completions/captn
```