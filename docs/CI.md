# Continuous Integration (CI) Setup

This document describes the CI/CD setup for the captn project.

## Overview

The project uses GitHub Actions for continuous integration, providing automated testing, code quality checks, and security scanning on every push and pull request.

## CI Workflow

The CI workflow (`.github/workflows/ci.yml`) includes the following jobs:

### 1. Test Job
- **Purpose**: Run unit and integration tests
- **Python Versions**: 3.9, 3.10, 3.11, 3.12
- **Features**:
  - Runs pytest with coverage reporting
  - Uploads coverage to Codecov
  - Uses dependency caching for faster builds

### 2. Lint Job
- **Purpose**: Code quality and style checks
- **Tools**:
  - **flake8**: Python linting
  - **black**: Code formatting check
  - **isort**: Import sorting check
  - **mypy**: Type checking

### 3. Security Job
- **Purpose**: Security vulnerability scanning
- **Tools**:
  - **bandit**: Python security linter
  - Uploads results to GitHub Security tab

### 4. Docker Build Job
- **Purpose**: Build and test Docker image
- **Features**:
  - Builds Docker image from Dockerfile
  - Tests basic functionality (--version, --help)
  - Runs after test, lint, and security jobs pass

### 5. Integration Test Job
- **Purpose**: Docker integration testing
- **Features**:
  - Runs only on pull requests
  - Tests container functionality in dry-run mode
  - Uses Docker-in-Docker for container testing

### 6. Pre-commit Job
- **Purpose**: Run pre-commit hooks
- **Features**:
  - Ensures code quality before merging
  - Runs all pre-commit checks on all files

## Local Development

### Prerequisites
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Running Tests Locally
```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run with coverage
make coverage
```

### Code Quality Checks
```bash
# Run all linting checks
make lint

# Format code
make format

# Security scanning
make security

# Run pre-commit hooks
make pre-commit
```

### Docker Testing
```bash
# Build Docker image
make docker-build

# Test Docker image
make docker-test
```

## Configuration Files

### pyproject.toml
- Configures pytest, black, isort, mypy, and bandit
- Defines project metadata and dependencies
- Sets up coverage reporting

### .pre-commit-config.yaml
- Defines pre-commit hooks for code quality
- Includes hooks for:
  - Basic file checks (trailing whitespace, YAML validation)
  - Code formatting (black, isort)
  - Linting (flake8, mypy)
  - Security scanning (bandit)

### requirements-dev.txt
- Development dependencies for testing and code quality
- Includes pytest, coverage tools, linting tools, and security scanners

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest configuration and fixtures
├── test_common.py           # Unit tests for common utilities
├── test_config.py           # Unit tests for configuration
└── test_integration.py      # Integration tests
```

### Test Categories

1. **Unit Tests** (`test_*.py`)
   - Test individual functions and classes
   - Use mocking to isolate units under test
   - Fast execution

2. **Integration Tests** (`test_integration.py`)
   - Test application as a whole
   - Test command-line interface
   - May require external dependencies (Docker)

3. **Fixtures** (`conftest.py`)
   - Shared test data and mocks
   - Common setup and teardown logic

## Coverage

The CI pipeline generates coverage reports for:
- **Terminal output**: Shows missing lines
- **HTML report**: Detailed coverage in `htmlcov/`
- **XML report**: For CI integration (Codecov)

## Security

Security scanning is performed using:
- **bandit**: Scans for common Python security issues
- **GitHub Security tab**: Displays security findings
- **Pre-commit hooks**: Prevent security issues from being committed

## Best Practices

1. **Write Tests**: Add tests for new features and bug fixes
2. **Run Locally**: Test changes locally before pushing
3. **Use Pre-commit**: Install pre-commit hooks to catch issues early
4. **Check Coverage**: Aim for high test coverage
5. **Security First**: Address security findings promptly

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `PYTHONPATH` includes the project root
2. **Docker Issues**: Ensure Docker is running and accessible
3. **Pre-commit Failures**: Run `pre-commit run --all-files` to see detailed errors
4. **Test Failures**: Check that all dependencies are installed

### Getting Help

- Check the GitHub Actions logs for detailed error information
- Review the test output for specific failure details
- Ensure your local environment matches the CI environment
