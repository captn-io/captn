# captn Documentation

<div align="center">
  <img src="../app/assets/icons/app-icon.svg" alt="captn logo" width="120" height="120">
  <h1>Intelligent Container Updater</h1>
</div>

---

## Welcome to captn

**captn** is an intelligent, rule-based container updater that automatically manages Docker container updates using semantic versioning and registry metadata. It provides a safe and controlled way to keep your containers up-to-date with configurable update policies and comprehensive verification mechanisms.

## What is captn?

captn is designed to automate the tedious task of keeping Docker containers updated while maintaining full control over what gets updated and when. Unlike simple "update everything" approaches, captn uses sophisticated rules to determine which updates are safe and appropriate for each container.

### Key Concepts

#### 1. Rule-Based Updates
captn uses configurable rules that define which types of updates are allowed for each container. For example:
- Production databases might only allow patch updates
- Development containers might accept all updates
- Security-critical services might only accept security and patch updates

#### 2. Semantic Versioning Support
captn understands semantic versioning and can differentiate between:
- **Major updates** (e.g., 1.x.x → 2.x.x): Breaking changes
- **Minor updates** (e.g., 1.1.x → 1.2.x): New features
- **Patch updates** (e.g., 1.1.1 → 1.1.2): Bug fixes
- **Build updates** (e.g., 1.1.1-1 → 1.1.1-2): Build variations
- **Digest updates**: Same tag, different image digest

#### 3. Progressive Upgrades
When multiple versions are available, captn can apply them in different ways based on the `progressiveUpgrade` setting in your rule configuration:
- **Progressive mode (`progressiveUpgrade: true`)**: All available updates are applied sequentially in a single captn run (e.g., 1.0 → 1.1 → 1.2 → 2.0), with verification after each step
- **Single-step mode (`progressiveUpgrade: false`)**: Only the next available update is applied per captn run (e.g., 1.0 → 1.1), with remaining updates applied in subsequent runs

#### 4. Verification & Rollback
After each update, captn verifies that the container starts successfully and remains stable. If an update fails, it automatically rolls back to the previous version.

## Core Features

For a complete feature overview, see the [README](https://github.com/captn-io/captn#features).

Key capabilities that make captn powerful:
- **Rule-Driven Updates**: Granular policies with conditional requirements and lag policies
- **Multi-Registry Support**: Docker Hub, GHCR, and private registries
- **Progressive Upgrades**: Sequential version updates with verification at each step
- **Safety Mechanisms**: Dry-run mode, automatic rollback, and verification periods
- **Notifications**: Real-time updates via Telegram and detailed email reports
- **Automation**: Built-in scheduler with cron support and container-specific scripts

## How captn Works

### Update Workflow

1. **Discovery**: captn scans your Docker environment for containers
2. **Filter**: Applies any filters you've specified (by name, status, etc.)
3. **Rule Evaluation**: For each container:
   - Determines which update rule applies
   - Fetches available image versions from the registry
   - Compares local version with remote versions
   - Determines update type (major, minor, patch, etc.)
4. **Pre-Script Execution**: Runs container-specific pre-update scripts
5. **Update**: Pulls new image and recreates the container
6. **Verification**: Monitors container stability for configured duration
7. **Post-Script Execution**: Runs container-specific post-update scripts
8. **Cleanup**: Removes old images and backup containers if configured
9. **Notification**: Sends update report via configured channels

### Safety Mechanisms

captn includes multiple safety mechanisms:

- **Dry-run mode**: Test without making changes
- **Backup containers**: Old containers are renamed and kept as backups
- **Verification period**: New containers must remain stable
- **Automatic rollback**: Failed updates are automatically reverted
- **Script timeouts**: Scripts have configurable execution timeouts
- **Minimal image age**: Only update images older than a specified age
- **Self-update protection**: Special handling for updating captn itself

## Documentation Structure

This documentation is organized into the following sections:

### [CLI Reference](02-CLI-Reference.md)
Complete command-line interface documentation including all parameters, filters, and usage examples.

### [Configuration](03-Configuration.md)
Comprehensive configuration reference covering all settings, sections, and options with detailed explanations and examples.

### [Pre/Post-Scripts](04-Scripts.md)
Guide to using pre-update and post-update scripts with practical examples and best practices.

## Quick Start

For installation instructions, see the [Quick Start section in the README](https://github.com/captn-io/captn#-quick-start).

After installation, configure update rules in `~/captn/conf/captn.cfg`:

```ini
[assignments]
# Assign containers to update rules
nginx = permissive
postgres = conservative
redis = patch_only
```

**Important:** Always test with `--dry-run` first:
```bash
docker exec captn captn --dry-run
```

## Use Cases

### Development Environments
Keep development containers automatically updated with the latest features:
```ini
[assignments]
dev-* = permissive
```

### Production Environments
Conservative updates with thorough verification:
```ini
[assignments]
prod-web = patch_only
prod-db = conservative
prod-cache = security_only
```

### Mixed Environments
Different rules for different services:
```ini
[assignments]
# Web servers: minor and patch updates
nginx = ci_cd
apache = ci_cd

# Databases: only patch updates
postgres = patch_only
mysql = patch_only

# Caches: all updates allowed
redis = permissive
memcached = permissive

# Critical services: security updates only
auth-service = security_only
payment-service = security_only
```

## Best Practices

### 1. Review Release Notes After Updates
**captn automates updates, but does not replace your responsibility.**

Even after successful automated updates by captn, always review the release notes of the updated image versions. Breaking changes, deprecated features, or new configuration requirements may have been introduced that are critical for continued operation.

### 2. Test Each Container Individually
**Not all containers are equal.**

Each image and container should be evaluated individually for automated updates:
- Some applications handle updates seamlessly
- Others require manual intervention or configuration changes

Start with non-critical containers and gradually expand to more critical services.

### 3. Implement a Backup Strategy
**captn does not replace your backup strategy.**

Automated updates increase the importance of regular backups. Consider what needs to be backed up!

**Backup considerations:**
- **Test your backups regularly** - verify they can actually be restored
- **Know your recovery procedure** - document and practice the restore process
- **Monitor backup success** - ensure backups are completing successfully

Remember: A backup that hasn't been tested is not a backup.

### 4. Start with Dry-Run
Always test your configuration with `--dry-run` before applying updates:
```bash
docker exec captn captn --dry-run
```

### 5. Use Conservative Rules Initially
Start with conservative update rules and gradually make them more permissive as you gain confidence:
```ini
[assignments]
# Start with patch_only or conservative - or a custom rule
myapp = patch_only
```

### 6. Schedule Updates During Low-Traffic Periods
Configure the cron schedule to run during maintenance windows:
```ini
[general]
cronSchedule = 0 3 * * *  # 3:00 AM daily
```

### 7. Keep Backup Containers
Configure cleanup policies to retain recent backups:
```ini
[prune]
removeOldContainers = true
minBackupAge = 48h
minBackupsToKeep = 1
```

## Common Scenarios

### Update a Single Container
```bash
docker exec captn captn --filter name=traefik
```

### Update Multiple Specific Containers
```bash
docker exec captn captn --filter name=immich-*
```

## Troubleshooting

### Container Not Being Updated

1. **Check logs**:
   ```bash
   docker exec captn captn --dry-run --log-level debug --clear-logs --filter name=mycontainer
   ```

2. **Check assigned rule**:
   - Verify rule assignment in `captn.cfg`
   - Check rule allows the available update type
   - Verify minimum image age requirement

### Update Failed or Rolled Back

1. **Check logs**:
   ```bash
   cat ~/captn/logs/captn.log
   ```

2. **Check verification settings**:
   ```ini
   [updateVerification]
   maxWait = 480s
   stableTime = 15s
   ```

3. **Try again in debug**:
   ```bash
   docker exec captn captn --log-level debug --clear-logs --filter name=mycontainer
   ```

4. **Inspect container logs**:
   ```bash
   docker logs mycontainer
   ```

### Script Execution Failures

1. **Verify script exists and is executable**:
   ```bash
   ls -la ~/captn/conf/scripts/
   chmod +x ~/captn/conf/scripts/*.sh
   ```

2. **Test script manually**:
   ```bash
   # Set environment variables
   export CAPTN_CONTAINER_NAME=mycontainer
   export CAPTN_SCRIPT_TYPE=pre
   export CAPTN_DRY_RUN=false
   
   # Run script
   ~/captn/conf/scripts/mycontainer_pre.sh
   ```

3. **Check script timeout**:
   ```ini
   [preScripts]
   timeout = 10m  # Increase if needed
   ```

## Getting Help

- **Documentation**: Read the detailed [Configuration](03-Configuration.md), [CLI Reference](02-CLI-Reference.md), and [Scripts](04-Scripts.md) documentation
- **Logs**: Check captn's logs with debug level enabled for detailed information
- **Dry-Run**: Use dry-run mode to understand what captn would do
- **GitHub Issues**: Report bugs or request features at [GitHub Issues](https://github.com/captn-io/captn/issues)
- **GitHub Discussions**: Ask questions at [GitHub Discussions](https://github.com/captn-io/captn/discussions)

---

**Next Steps**:
- [CLI Reference →](02-CLI-Reference.md)
- [Configuration Guide →](03-Configuration.md)
- [Scripts Guide →](04-Scripts.md)

---

<div align="center">
  <p>Brewed with ❤️ and loads of 🍺</p>
</div>
