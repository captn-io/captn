# Development Environment

This directory contains scripts and configuration for setting up the captn development environment.

## Quick Start

### Option 1: Containerized Development (Recommended)

```bash
# Start development container
./dev/scripts/dev-setup-containered.sh
```

This will:
- Build a development Docker image based on the production image
- Mount your project files into the container
- Install development tools (git, vim, nano, pytest, black, flake8, mypy)
- Start an interactive bash shell

### Option 2: Local Development

```bash
# Set up local development environment
./dev/scripts/dev-setup.sh
```

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

# Development tools
pytest                    # Run tests
black app/               # Format code
flake8 app/              # Lint code
mypy app/               # Type checking
isort app/              # Sort imports

# Legacy compatibility
cu --help               # Short command
dcu --help              # Docker container updater
container-updater --help # Full legacy name
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
./dev/scripts/dev-setup-containered.sh
```

## Tips

1. **File Editing**: Edit files on your host system - changes are immediately reflected in the container
2. **Persistence**: Installed packages in the container are lost when it exits, but project files persist
3. **Testing**: Use `pytest` to run tests within the container
4. **Debugging**: Use `captn --dry-run` to test without making actual changes