# Development Environment

This directory contains scripts and configuration for setting up the captn development environment.

## Quick Start

### Containerized Development (Recommended)

```bash
# Start development container
./dev/scripts/dev-setup.sh
```

This will:
- Build a development Docker image based on the production image
- Mount your project files into the container
- Install development tools (git, vim, nano, pytest, black, flake8, mypy)
- Start an interactive bash shell

## Development Container Features

- **Base**: Same as production (Alpine Linux + Python)
- **Development Tools**: git, vim, nano, curl, jq, make, gcc
- **Python Tools**: pytest, black, flake8, mypy, isort
- **Persistent Volumes**:
  - `captn-dev-cache`: Pip cache for faster installs
  - `captn-dev-venv`: Virtual environment persistence
- **File Mounting**: Project files are mounted from host
- **Docker Access**: Docker socket is mounted for container management

## Available Commands in Development Container

```bash
# Run captn
captn --help
captn --version
captn --dry-run

# Run via Python module
python -m app --help

# Auto-completion is available in development container
captn --<Tab>                     # Shows all available options
captn --log-level <Tab>           # Shows log levels

# Development tools
pytest                            # Run tests
black app/                        # Format code
flake8 app/                       # Lint code
mypy app/                         # Type checking
isort app/                        # Sort imports
```

### Adding New Command Line Parameters

When implementing new command line parameters, you need to update the auto-completion scripts to keep Tab completion working:

#### 1. Update the Argument Parser (`app/__main__.py`)

Add your new parameter to the `parse_args()` function:

```python
parser.add_argument(
    "--new-param", "-n",
    choices=["option1", "option2", "option3"],  # If it has choices
    help="Description of the new parameter"
)
```

#### 2. Update Auto-Completion Scripts

**For Docker environments (`app/cli/scripts/captn-cli-completion.sh`):**

Add your new parameter to the `opts` variable:
```bash
opts="--version --force --run --dry-run --filter --log-level --new-param --help -v -f -r -t -l -n -h"
```

If your parameter has choices, add completion logic:
```bash
# Handle --new-param argument completion
if [[ ${prev} == "--new-param" ]] || [[ ${prev} == "-n" ]]; then
    local choices="option1 option2 option3"
    COMPREPLY=($(compgen -W "${choices}" -- "${cur}"))
    return 0
fi
```

**For Python argcomplete (`app/__main__.py`):**

If your parameter has choices, they're automatically handled by argparse. For custom completion, add a completer function:

```python
def new_param_completer(prefix, parsed_args, **kwargs):
    """Custom completer for --new-param argument."""
    choices = ["option1", "option2", "option3"]
    return [choice for choice in choices if choice.startswith(prefix)]

# In parse_args(), after creating the argument:
if argcomplete:
    new_param_arg.completer = new_param_completer
```

#### 3. Update Tests

Add tests for your new parameter in `tests/test_autocomplete.py`:

```python
def test_new_param_completer(self):
    """Test completer for new parameter."""
    completions = new_param_completer("opt", None)
    assert completions == ["option1", "option2", "option3"]
```

#### 4. Update Documentation

- Update this README.md with the new parameter in the command line options section

#### Example: Adding a `--registry` Parameter

```python
# In app/__main__.py
parser.add_argument(
    "--registry", "-R",
    choices=["docker", "ghcr", "custom"],
    help="Specify registry type"
)

# In app/cli/scripts/captn-cli-completion.sh
opts="--version --force --run --dry-run --filter --log-level --registry --help -v -f -r -t -l -R -h"

# Add completion logic
if [[ ${prev} == "--registry" ]] || [[ ${prev} == "-R" ]]; then
    local registries="docker ghcr custom"
    COMPREPLY=($(compgen -W "${registries}" -- "${cur}"))
    return 0
fi
```

## Configuration

The development container uses the same configuration as production:
- Configuration file: `/app/conf/captn.cfg`
- Log directory: `/app/logs/`
- Working directory: `/app`

## Volumes

- **captn-dev-cache**: Persistent pip cache
- **captn-dev-venv**: Persistent virtual environment
- **Project files**: Mounted from host (changes persist)

## Rebuilding

The development image is automatically rebuilt when:
- The Dockerfile is newer than the existing image
- The image doesn't exist

To force rebuild:
```bash
docker rmi captn:dev
./dev/scripts/dev-setup.sh
```

## Tips

1. **File Editing**: Edit files on your host system - changes are immediately reflected in the container
2. **Persistence**: Installed packages in the container are lost when it exits, but project files persist
3. **Testing**: Use `pytest` to run tests within the container
4. **Debugging**: Use `captn --dry-run` to test without making actual changes+
