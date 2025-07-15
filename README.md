<div align="center">
  <img src="assets/icons/app-icon.svg" alt="captn logo" width="120" height="120">
</div>

---

<p align="center">
  An intelligent, rule-based tool that automatically updates containers using semantic versioning and registry metadata.<br>
</p>

Captn intelligently manages container updates with sophisticated rules, self-update capabilities, and comprehensive logging.


## 🚀 Features

- **Rule-Driven Updates**: Define custom rules for different containers and update types
- **Semantic Versioning**: Supports major, minor, patch, build, and digest-based updates
- **Self-Update Capability**: Can update itself while running inside a container
- **Multiple Registry Support**: Docker Hub, GitHub Container Registry (GHCR), and generic registries
- **Progressive Upgrades**: Option to apply multiple updates in sequence
- **Dry-Run Mode**: Preview changes before applying them
- **Container Filtering**: Filter containers by name and status
- **Automatic Cleanup**: Remove unused images and old containers
- **Comprehensive Logging**: Detailed logging with configurable levels
- **Cron Integration**: Scheduled execution via cron
- **Lock Mechanism**: Prevents multiple instances from running simultaneously

## 📋 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage](#usage)
- [Rules System](#rules-system)
- [Self-Update](#self-update)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

## 🛠️ Installation

### Docker Installation (Recommended)

```bash
# Pull the latest image
docker pull ghcr.io/janseppenrade2/container-updater:latest

# Or build from source
git clone https://github.com/janseppenrade2/container-updater.git
cd container-updater
docker build -f docker/DOCKERFILE -t container-updater .
```

### Local Installation

```bash
# Clone the repository
git clone https://github.com/janseppenrade2/container-updater.git
cd container-updater

# Install dependencies
pip install -r requirements.txt

# Make the script executable
chmod +x app/container-updater.sh
```

## 🚀 Quick Start

### Basic Docker Run

```bash
docker run -d \
  --name container-updater \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /path/to/config:/app/conf \
  -e CRON_SCHEDULE="0 2 * * *" \
  ghcr.io/janseppenrade2/container-updater:latest
```

### Manual Execution

```bash
# Run with default settings (dry-run mode)
python -m app

# Run with actual updates
python -m app --run

# Run with custom filters
python -m app --run --filter name=nginx name=redis status=running

# Run with debug logging
python -m app --run --log-level debug
```

## ⚙️ Configuration

The container updater uses a configuration file located at `/app/conf/container-updater.cfg`. You can also use environment variables for all settings.

### Configuration File Structure

```ini
[general]
dryRun = true

[update]
delayBetweenUpdates = 15s

[updateVerification]
maxWait = 480s
stableTime = 15s
checkInterval = 5s
gracePeriod = 15s

[prune]
removeUnusedImages = true
removeOldContainers = true
minBackupAge = 48h
minBackupsToKeep = 1

[docker]
apiUrl = https://registry.hub.docker.com/v2
pageCrawlLimit = 1000
pageSize = 100

[ghcr]
apiUrl = https://ghcr.io/v2
pageCrawlLimit = 1000
pageSize = 100

[logging]
level = INFO

[assignmentsByName]
nginx = strict
redis = permissive
postgres = conservative

[rules]
default = {
    "minImageAge": "3h",
    "progressiveUpgrade": false,
    "allow": {
        "major": false,
        "minor": false,
        "patch": true,
        "build": false,
        "digest": false
    }
}
```

### Environment Variables

All configuration options can be set via environment variables using the pattern `SECTION_OPTION`:

```bash
# General settings
export GENERAL_DRYRUN=false

# Update settings
export UPDATE_DELAYBETWEENUPDATES=30s

# Logging
export LOGGING_LEVEL=DEBUG

# Container assignments
export ASSIGNMENTSBYNAME_NGINX=strict
export ASSIGNMENTSBYNAME_REDIS=permissive

# Custom rules
export RULES_MYCUSTOMRULE='{"minImageAge": "1h", "allow": {"patch": true}}'
```

## 📖 Usage

### Command Line Options

```bash
python -m app [OPTIONS]

Options:
  --version, -v             Display the current version
  --force, -f               Force lock acquisition
  --run, -r                 Force actual execution without dry-run
  --dry-run, -t             Run in dry-run/test mode
  --filter FILTER           Filter containers to process
  --log-level, -l           Set logging level (debug, info, warning, error, critical)
  --clear-logs, -c          Delete all log files before starting
```

### Container Filtering

Filter containers by name and status:

```bash
# Filter by exact name
python -m app --filter name=nginx

# Filter by wildcard pattern
python -m app --filter name=ngin* name=*cloud*

# Filter by status
python -m app --filter status=running

# Combine filters
python -m app --filter name=webapp status=all
```

### Examples

```bash
# Preview what would be updated
python -m app --dry-run

# Update specific containers
python -m app --run --filter name=nginx name=redis

# Update with debug logging
python -m app --run --log-level debug --filter name=postgres

# Force execution (override config dry-run setting)
python -m app --run --force

# Delete logs and run with debug logging
python -m app --clear-logs --log-level debug --dry-run
```

## 🎯 Rules System

The rules system allows you to define update policies for different containers and update types.

### Rule Properties

| Property | Type | Description |
|----------|------|-------------|
| `minImageAge` | string | Minimum age required for images (e.g., "3h", "24h") |
| `progressiveUpgrade` | boolean | Whether to apply multiple updates in sequence |
| `allow` | object | Which update types are allowed |
| `conditions` | object | Conditions that must be met for updates |
| `lagPolicy` | object | Version lag requirements |

### Update Types

- **major**: Major version updates (e.g., 1.0.0 → 2.0.0)
- **minor**: Minor version updates (e.g., 1.0.0 → 1.1.0)
- **patch**: Patch version updates (e.g., 1.0.0 → 1.0.1)
- **build**: Build number updates (e.g., 1.0.0 → 1.0.0+build.123)
- **digest**: Digest-based updates (same tag, different digest)

### Predefined Rules

#### default
Conservative rule that only allows patch updates:
```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": false,
    "allow": {
        "major": false,
        "minor": false,
        "patch": true,
        "build": false,
        "digest": false
    }
}
```

#### relaxed
Allows all update types with progressive upgrades:
```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": true,
    "allow": {
        "major": true,
        "minor": true,
        "patch": true,
        "build": true,
        "digest": true
    },
    "conditions": {
        "major": {
            "require": ["minor", "patch", "build"]
        }
    }
}
```

#### strict
Very conservative, no updates allowed:
```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": false,
    "allow": {
        "major": false,
        "minor": false,
        "patch": false,
        "build": false,
        "digest": false
    }
}
```

#### permissive
Allows all updates without conditions:
```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": true,
    "allow": {
        "major": true,
        "minor": true,
        "patch": true,
        "build": true,
        "digest": true
    }
}
```

#### patch_only
Only allows patch updates:
```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": false,
        "patch": true,
        "build": false,
        "digest": false
    }
}
```

#### security_only
Only allows security-related updates (patch and digest):
```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": false,
        "patch": true,
        "build": false,
        "digest": true
    }
}
```

#### ci_cd
Suitable for CI/CD environments:
```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": true,
        "patch": true,
        "build": true,
        "digest": false
    },
    "conditions": {
        "minor": {
            "require": ["patch"]
        }
    }
}
```

#### conservative
Conservative with longer minimum age:
```json
{
    "minImageAge": "24h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": false,
        "patch": true,
        "build": true,
        "digest": false
    },
    "lagPolicy": {
        "major": 1
    }
}
```

### Container Assignment

Assign rules to containers by name:

```ini
[assignmentsByName]
nginx = strict
redis = permissive
postgres = conservative
webapp = ci_cd
```

## 🔄 Self-Update

The container updater can update itself while running inside a Docker container. This feature is automatically detected and handled.

### How Self-Update Works

1. **Detection**: The system automatically detects if it's running inside a container
2. **Deferral**: Self-updates are scheduled for the end of the update cycle
3. **Helper Container**: A helper container is created with the new image
4. **Execution**: The helper container runs the updater to update the original container
5. **Cleanup**: Helper containers are automatically removed

### Self-Update Configuration

Self-updates use the same rule system as other containers. Configure via the `[assignmentsByName]` section:

```ini
[assignmentsByName]
Container-Updater = default
```

### Self-Update Requirements

- Container must be running inside Docker
- Docker socket access required
- Proper restart policy configured
- Same image base as the update target

## 🔧 API Reference

### Configuration Sections

#### [general]
- `dryRun` (boolean): Default dry-run mode

#### [update]
- `delayBetweenUpdates` (duration): Delay between updates for the same container

#### [updateVerification]
- `maxWait` (duration): Maximum time to wait for container stability
- `stableTime` (duration): Time container must be stable
- `checkInterval` (duration): How often to check container status
- `gracePeriod` (duration): Grace period after container start

#### [prune]
- `removeUnusedImages` (boolean): Remove unused images
- `removeOldContainers` (boolean): Remove old container backups
- `minBackupAge` (duration): Minimum age for backup removal
- `minBackupsToKeep` (integer): Minimum backups to keep

#### [docker]
- `apiUrl` (string): Docker Hub API URL
- `pageCrawlLimit` (integer): Maximum pages to crawl
- `pageSize` (integer): Tags per page

#### [ghcr]
- `apiUrl` (string): GitHub Container Registry API URL
- `pageCrawlLimit` (integer): Maximum pages to crawl
- `pageSize` (integer): Tags per page

#### [logging]
- `level` (string): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

#### [assignmentsByName]
- Container name assignments to rules

#### [rules]
- Custom rule definitions

## 📝 Examples

### Basic Configuration

```ini
[general]
dryRun = false

[update]
delayBetweenUpdates = 30s

[logging]
level = INFO

[assignmentsByName]
nginx = strict
redis = permissive
postgres = conservative

[rules]
default = {
    "minImageAge": "3h",
    "progressiveUpgrade": false,
    "allow": {
        "major": false,
        "minor": false,
        "patch": true,
        "build": false,
        "digest": false
    }
}
```

### Production Configuration

```ini
[general]
dryRun = false

[update]
delayBetweenUpdates = 60s

[updateVerification]
maxWait = 600s
stableTime = 30s
checkInterval = 10s
gracePeriod = 30s

[prune]
removeUnusedImages = true
removeOldContainers = true
minBackupAge = 168h
minBackupsToKeep = 3

[logging]
level = INFO

[assignmentsByName]
webapp = ci_cd
database = conservative
cache = permissive
monitoring = patch_only

[rules]
ci_cd = {
    "minImageAge": "1h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": true,
        "patch": true,
        "build": true,
        "digest": false
    },
    "conditions": {
        "minor": {
            "require": ["patch"]
        }
    }
}
```

### Docker Compose Example

```yaml
version: '3.8'

services:
  container-updater:
    image: ghcr.io/janseppenrade2/container-updater:latest
    container_name: container-updater
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./config:/app/conf
    environment:
      - CRON_SCHEDULE=0 2 * * *
      - LOGGING_LEVEL=INFO
      - GENERAL_DRYRUN=false
    networks:
      - default
```

## 🐛 Troubleshooting

### Common Issues

#### Container Not Detected
- Ensure Docker socket is mounted correctly
- Check container is running and accessible
- Verify container name matches expectations

#### Updates Not Applied
- Check dry-run mode is disabled
- Verify rule configuration allows updates
- Check minimum image age requirements
- Review container assignment rules

#### Self-Update Issues
- Ensure container is running inside Docker
- Verify Docker socket access
- Check restart policy configuration
- Review self-update rule assignment

#### Permission Errors
- Ensure proper Docker socket permissions
- Check container has sufficient privileges
- Verify file system permissions

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
python -m app --log-level debug --dry-run
```

### Lock Issues

If the updater reports another instance is running:

```bash
# Remove lock file manually (use with caution)
rm -f /tmp/container-updater.lock
```

### Log Analysis

Check logs for specific error patterns:

```bash
# View recent logs
docker logs container-updater --tail 100

# Follow logs in real-time
docker logs container-updater -f
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 🚀 CI/CD

This project uses GitHub Actions for continuous integration and deployment. The workflow automatically builds and publishes Docker images to DockerHub.

### Automated Builds

- **Triggered on**: Push to `main` branch and release tags (`v*`)
- **Multi-platform**: Supports `linux/amd64` and `linux/arm64`
- **Security scanning**: Includes Trivy and Snyk vulnerability scanning
- **Automated testing**: Pulls and tests built images

### Docker Images

Images are published to DockerHub under `captn-io/captn`:

```bash
# Pull the latest image
docker pull captn-io/captn:latest

# Pull a specific version
docker pull captn-io/captn:v1.0.0

# Pull development build
docker pull captn-io/captn:dev
```

### Setup Requirements

To enable automated publishing, add these secrets to your GitHub repository:

- `DOCKERHUB_USERNAME`: Your DockerHub username
- `DOCKERHUB_TOKEN`: Your DockerHub access token
- `SNYK_TOKEN`: (Optional) Snyk API token for security scanning

For detailed setup instructions, see [`.github/workflows/README.md`](.github/workflows/README.md).

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with Python and Docker
- Supports multiple container registries
- Inspired by the need for automated container management
