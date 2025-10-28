# Pre/Post-Scripts Guide

This document provides comprehensive guidance on using pre-update and post-update scripts with captn.

## Table of Contents

- [Overview](#overview)
- [How Scripts Work](#how-scripts-work)
- [Script Types](#script-types)
- [Script Discovery](#script-discovery)
- [Environment Variables](#environment-variables)
- [Script Guidelines](#script-guidelines)
- [Configuration](#configuration)
- [Generic Scripts](#generic-scripts)
- [Container-Specific Scripts](#container-specific-scripts)
- [Example Scripts](#example-scripts)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

Pre and post-update scripts allow you to execute custom logic before and after container updates. They provide flexibility to handle:

- **Pre-Scripts:**
  - Database backups
  - Data snapshots
  - Health checks
  - Service dependencies (pause/unpause)
  - Pre-flight validations
  - Custom preparation tasks

- **Post-Scripts:**
  - Health verification
  - Database migrations
  - Service restart coordination
  - Custom post-update tasks
  - Cleanup operations
  - Notification triggers

---

## How Scripts Work

### Execution Flow

```
1. Container Selected for Update
       ↓
2. Pre-Script Execution
       ↓
3. Image Pull
       ↓
4. Container Recreation
       ↓
5. Container Verification
       ↓
6. Post-Script Execution
       ↓
7. Update Complete
```

### Failure Handling

**Pre-Script Failure:**
- If `continueOnFailure = false` (default): Update is aborted
- If `continueOnFailure = true`: Update proceeds despite failure

**Post-Script Failure:**
- If `rollbackOnFailure = true` (default): Container is rolled back to previous version
- If `rollbackOnFailure = false`: Update is considered successful

---

## Script Types

### Pre-Scripts

Executed **before** the container is updated.

**Purpose:**
- Prepare the system for update
- Backup data
- Pause dependent services
- Verify pre-conditions

**Naming Convention:**
- **Container-specific:** `<container_name>_pre.sh`
- **Generic:** `pre.sh`

**Example:**
```bash
# /app/conf/scripts/database_pre.sh
# /app/conf/scripts/pre.sh
```

### Post-Scripts

Executed **after** the container has been successfully recreated and verified.

**Purpose:**
- Verify update success
- Run migrations
- Resume dependent services
- Perform post-update tasks

**Naming Convention:**
- **Container-specific:** `<container_name>_post.sh`
- **Generic:** `post.sh`

**Example:**
```bash
# /app/conf/scripts/database_post.sh
# /app/conf/scripts/post.sh
```

---

## Script Discovery

captn follows a specific discovery order when looking for scripts:

### Priority Order

1. **Container-Specific Script:** `<container_name>_pre.sh` or `<container_name>_post.sh`
2. **Generic Script:** `pre.sh` or `post.sh`
3. **No Script:** If neither exists, script execution is skipped (not an error)

### Example

For a container named `postgres`:

**Pre-Script Discovery:**
1. Look for: `/app/conf/scripts/postgres_pre.sh` ✓ Use if found
2. Look for: `/app/conf/scripts/pre.sh` ✓ Use if found (and #1 not found)
3. No script found → Skip pre-script execution

**Post-Script Discovery:**
1. Look for: `/app/conf/scripts/postgres_post.sh` ✓ Use if found
2. Look for: `/app/conf/scripts/post.sh` ✓ Use if found (and #1 not found)
3. No script found → Skip post-script execution

---

## Environment Variables

captn provides several environment variables to scripts:

### Available Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `CAPTN_CONTAINER_NAME` | Name of the container being updated | `nginx` |
| `CAPTN_SCRIPT_TYPE` | Type of script (`pre` or `post`) | `pre` |
| `CAPTN_DRY_RUN` | Whether this is a dry-run | `true` or `false` |
| `CAPTN_LOG_LEVEL` | Current log level | `INFO` |
| `CAPTN_CONFIG_DIR` | captn configuration directory | `/app/conf` |
| `CAPTN_SCRIPTS_DIR` | Scripts directory | `/app/conf/scripts` |

### Using Environment Variables

```bash
#!/bin/bash

echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"

if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would perform backup..."
    exit 0
fi

# Actual backup logic
perform_backup "$CAPTN_CONTAINER_NAME"
```

---

## Script Guidelines

### Basic Requirements

1. **Shebang:** Start with `#!/bin/bash`
2. **Execute Permission:** Script must be executable (`chmod +x`)
3. **Exit Code:**
   - `0` = Success
   - Non-zero = Failure
4. **Error Handling:** Use `set -e` to exit on errors
5. **Logging:** Use `echo` for output (captured by captn)

### Script Template

```bash
#!/bin/bash
# Description of what this script does

set -e  # Exit on error

echo "=== Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Timestamp: $(date)"

# Handle dry-run mode
if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would perform actions..."
    echo "=== Script Completed (Dry-Run) ==="
    exit 0
fi

# Actual script logic here
echo "Performing actual actions..."

# Your commands here

echo "=== Script Completed ==="
exit 0
```

### Error Handling

```bash
#!/bin/bash
set -e  # Exit immediately on error

# Trap errors and provide context
trap 'echo "Error on line $LINENO"; exit 1' ERR

# Verify prerequisites
if ! docker ps > /dev/null 2>&1; then
    echo "Error: Cannot connect to Docker"
    exit 1
fi

# Check container exists
if ! docker ps -a --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
    echo "Error: Container $CAPTN_CONTAINER_NAME not found"
    exit 1
fi
```

---

## Configuration

### Script Configuration

```ini
[preScripts]
enabled = true
scriptsDirectory = /app/conf/scripts
timeout = 10m
continueOnFailure = false

[postScripts]
enabled = true
scriptsDirectory = /app/conf/scripts
timeout = 10m
rollbackOnFailure = true
```

### Configuration Options

#### Pre-Scripts

- **enabled:** Enable/disable pre-script execution
- **scriptsDirectory:** Directory containing scripts
- **timeout:** Maximum execution time
- **continueOnFailure:** Continue update if pre-script fails

#### Post-Scripts

- **enabled:** Enable/disable post-script execution
- **scriptsDirectory:** Directory containing scripts
- **timeout:** Maximum execution time
- **rollbackOnFailure:** Rollback container if post-script fails

---

## Generic Scripts

Generic scripts apply to all containers that don't have container-specific scripts.

### Generic Pre-Script

**File:** `/app/conf/scripts/pre.sh`

```bash
#!/bin/bash
# Generic Pre-Update Script
# This script is executed before container updates

set -e

echo "=== Pre-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Timestamp: $(date)"

if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would perform pre-update tasks..."
    echo "=== Pre-Update Script Completed (Dry-Run) ==="
    exit 0
fi

# Verify container is running
if docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
    echo "Container $CAPTN_CONTAINER_NAME is running"
else
    echo "Warning: Container $CAPTN_CONTAINER_NAME is not running"
fi

# Generic health check
echo "Performing generic health check..."
docker inspect "$CAPTN_CONTAINER_NAME" > /dev/null 2>&1 || {
    echo "Error: Cannot inspect container"
    exit 1
}

# Log container status
docker ps --filter "name=^${CAPTN_CONTAINER_NAME}$" --format "Status: {{.Status}}"

echo "=== Pre-Update Script Completed ==="
exit 0
```

### Generic Post-Script

**File:** `/app/conf/scripts/post.sh`

```bash
#!/bin/bash
# Generic Post-Update Script
# This script is executed after container updates

set -e

echo "=== Post-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Timestamp: $(date)"

if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would perform post-update tasks..."
    echo "=== Post-Update Script Completed (Dry-Run) ==="
    exit 0
fi

# Verify container is running
if docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
    echo "Container $CAPTN_CONTAINER_NAME is running successfully"
else
    echo "Error: Container $CAPTN_CONTAINER_NAME is not running"
    exit 1
fi

# Generic health check
echo "Performing generic health check..."
HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CAPTN_CONTAINER_NAME" 2>/dev/null || echo "none")

if [ "$HEALTH_STATUS" = "healthy" ] || [ "$HEALTH_STATUS" = "none" ]; then
    echo "Health check passed: $HEALTH_STATUS"
else
    echo "Warning: Health status is $HEALTH_STATUS"
fi

echo "=== Post-Update Script Completed ==="
exit 0
```

---

## Container-Specific Scripts

Container-specific scripts override generic scripts and provide tailored logic.

### Database Pre-Script Example

**File:** `/app/conf/scripts/PostgreSQL_pre.sh`

```bash
#!/bin/bash
# PostgreSQL-specific Pre-Update Script
# Performs database backup and pauses dependent containers

set -e

echo "=== PostgreSQL Pre-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Timestamp: $(date)"

BACKUP_DIR="/var/backups/postgresql"

if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would create backup of PostgreSQL data"
    echo "Would pause dependent containers"
    echo "=== Pre-Update Script Completed (Dry-Run) ==="
    exit 0
fi

# Verify container is running
if ! docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
    echo "Error: Container $CAPTN_CONTAINER_NAME is not running"
    exit 1
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Get list of databases
echo "Fetching list of databases..."
DB_NAMES=$(docker exec -i "$CAPTN_CONTAINER_NAME" psql -U postgres -t -c \
    "SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres';")


# Pause dependent containers
echo "Pausing dependent containers..."
for db_name in $DB_NAMES; do
    # Check if container with database name exists
    if docker ps --format "{{.Names}}" | grep -q "^${db_name}$"; then
        echo "Pausing container: $db_name"
        docker pause "$db_name"
    else
        # Check for containers starting with database name
        DEPENDENT_CONTAINERS=$(docker ps --format "{{.Names}}" | grep "^${db_name}-" || true)
        for container in $DEPENDENT_CONTAINERS; do
            echo "Pausing container: $container"
            docker pause "$container"
        done
    fi
done

# Backup each database
for db_name in $DB_NAMES; do
    echo "Backing up database: $db_name"
    docker exec -i "$CAPTN_CONTAINER_NAME" pg_dump -U postgres "$db_name" | \
        gzip > "$BACKUP_DIR/${db_name}_$(date +%Y%m%d_%H%M%S).sql.gz"
done

echo "=== PostgreSQL Pre-Update Script Completed ==="
exit 0
```

### Database Post-Script Example

**File:** `/app/conf/scripts/PostgreSQL_post.sh`

```bash
#!/bin/bash
# PostgreSQL-specific Post-Update Script
# Unpauses dependent containers and verifies database health

set -e

echo "=== PostgreSQL Post-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Timestamp: $(date)"

if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would verify database health"
    echo "Would unpause dependent containers"
    echo "=== Post-Update Script Completed (Dry-Run) ==="
    exit 0
fi

# Verify container is running
if ! docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
    echo "Error: Container $CAPTN_CONTAINER_NAME is not running"
    exit 1
fi

# Verify PostgreSQL is responsive
echo "Verifying PostgreSQL is responsive..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec "$CAPTN_CONTAINER_NAME" pg_isready -U postgres > /dev/null 2>&1; then
        echo "PostgreSQL is ready"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for PostgreSQL to be ready... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Error: PostgreSQL did not become ready in time"
    exit 1
fi

# Get list of databases
echo "Fetching list of databases..."
DB_NAMES=$(docker exec -i "$CAPTN_CONTAINER_NAME" psql -U postgres -t -c \
    "SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres';")

# Unpause dependent containers
echo "Unpausing dependent containers..."
for db_name in $DB_NAMES; do
    # Check if container with database name exists and is paused
    if docker ps -a --filter "name=^${db_name}$" --filter "status=paused" --format "{{.Names}}" | grep -q "^${db_name}$"; then
        echo "Unpausing container: $db_name"
        docker unpause "$db_name"
    else
        # Check for paused containers starting with database name
        PAUSED_CONTAINERS=$(docker ps -a --filter "status=paused" --format "{{.Names}}" | grep "^${db_name}-" || true)
        for container in $PAUSED_CONTAINERS; do
            echo "Unpausing container: $container"
            docker unpause "$container"
        done
    fi
done

echo "=== PostgreSQL Post-Update Script Completed ==="
exit 0
```

---

## Example Scripts

### Redis Pre-Script

**File:** `/app/conf/scripts/redis_pre.sh`

```bash
#!/bin/bash
# Redis Pre-Update Script
# Triggers Redis save before update

set -e

echo "=== Redis Pre-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Timestamp: $(date)"

if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would trigger Redis SAVE command"
    echo "=== Redis Pre-Update Script Completed (Dry-Run) ==="
    exit 0
fi

# Verify container is running
if ! docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
    echo "Error: Container $CAPTN_CONTAINER_NAME is not running"
    exit 1
fi

# Trigger Redis save
echo "Triggering Redis SAVE command..."
docker exec "$CAPTN_CONTAINER_NAME" redis-cli SAVE

echo "Redis data saved successfully"
echo "=== Redis Pre-Update Script Completed ==="
exit 0
```

### Redis Post-Script

**File:** `/app/conf/scripts/redis_post.sh`

```bash
#!/bin/bash
# Redis Post-Update Script
# Verifies Redis is responsive

set -e

echo "=== Redis Post-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Timestamp: $(date)"

if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would verify Redis health"
    echo "=== Redis Post-Update Script Completed (Dry-Run) ==="
    exit 0
fi

# Verify container is running
if ! docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
    echo "Error: Container $CAPTN_CONTAINER_NAME is not running"
    exit 1
fi

# Test Redis connectivity
echo "Testing Redis connectivity..."
if docker exec "$CAPTN_CONTAINER_NAME" redis-cli PING | grep -q "PONG"; then
    echo "Redis is responsive"
else
    echo "Error: Redis is not responding"
    exit 1
fi

# Check Redis info
echo "Checking Redis info..."
docker exec "$CAPTN_CONTAINER_NAME" redis-cli INFO server | grep "redis_version"

echo "=== Redis Post-Update Script Completed ==="
exit 0
```

### Nextcloud Post-Script

**File:** `/app/conf/scripts/Nextcloud_post.sh`

```bash
#!/bin/bash
# Nextcloud Post-Update Script
# Runs database migrations and maintenance tasks

set -e

echo "=== Nextcloud Post-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Timestamp: $(date)"

if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would run Nextcloud maintenance tasks"
    echo "=== Nextcloud Post-Update Script Completed (Dry-Run) ==="
    exit 0
fi

# Verify container is running
if ! docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
    echo "Error: Container $CAPTN_CONTAINER_NAME is not running"
    exit 1
fi

# Enable maintenance mode
echo "Enabling maintenance mode..."
docker exec -u www-data "$CAPTN_CONTAINER_NAME" php occ maintenance:mode --on

# Run database migrations
echo "Running database migrations..."
docker exec -u www-data "$CAPTN_CONTAINER_NAME" php occ upgrade

# Add missing database indices
echo "Adding missing database indices..."
docker exec -u www-data "$CAPTN_CONTAINER_NAME" php occ db:add-missing-indices

# Add missing columns
echo "Adding missing database columns..."
docker exec -u www-data "$CAPTN_CONTAINER_NAME" php occ db:add-missing-columns

# Disable maintenance mode
echo "Disabling maintenance mode..."
docker exec -u www-data "$CAPTN_CONTAINER_NAME" php occ maintenance:mode --off

# Verify Nextcloud is accessible
echo "Verifying Nextcloud status..."
docker exec -u www-data "$CAPTN_CONTAINER_NAME" php occ status

echo "=== Nextcloud Post-Update Script Completed ==="
exit 0
```

### Web Server Pre-Script

**File:** `/app/conf/scripts/nginx_pre.sh`

```bash
#!/bin/bash
# Nginx Pre-Update Script
# Validates configuration before update

set -e

echo "=== Nginx Pre-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Timestamp: $(date)"

if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would validate Nginx configuration"
    echo "=== Nginx Pre-Update Script Completed (Dry-Run) ==="
    exit 0
fi

# Verify container is running
if ! docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
    echo "Error: Container $CAPTN_CONTAINER_NAME is not running"
    exit 1
fi

# Test Nginx configuration
echo "Testing Nginx configuration..."
if docker exec "$CAPTN_CONTAINER_NAME" nginx -t; then
    echo "Nginx configuration is valid"
else
    echo "Error: Nginx configuration is invalid"
    exit 1
fi

echo "=== Nginx Pre-Update Script Completed ==="
exit 0
```

### Application with API Health Check

**File:** `/app/conf/scripts/webapp_post.sh`

```bash
#!/bin/bash
# WebApp Post-Update Script
# Verifies API health endpoint

set -e

echo "=== WebApp Post-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Timestamp: $(date)"

API_HEALTH_URL="http://localhost:8080/health"

if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would check API health endpoint: $API_HEALTH_URL"
    echo "=== WebApp Post-Update Script Completed (Dry-Run) ==="
    exit 0
fi

# Verify container is running
if ! docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
    echo "Error: Container $CAPTN_CONTAINER_NAME is not running"
    exit 1
fi

# Wait for application to be ready
echo "Waiting for application to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Check health endpoint
    HTTP_CODE=$(docker exec "$CAPTN_CONTAINER_NAME" wget -q -O - --server-response "$API_HEALTH_URL" 2>&1 | grep "HTTP/" | awk '{print $2}' || echo "000")
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo "Application health check passed (HTTP $HTTP_CODE)"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for application... ($RETRY_COUNT/$MAX_RETRIES) - HTTP $HTTP_CODE"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Error: Application did not become healthy in time"
    exit 1
fi

echo "=== WebApp Post-Update Script Completed ==="
exit 0
```

---

## Best Practices

### 1. Always Handle Dry-Run Mode

```bash
if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would perform actions..."
    exit 0
fi
```

### 2. Verify Prerequisites

```bash
# Check container exists and is running
if ! docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
    echo "Error: Container not running"
    exit 1
fi
```

### 3. Use Appropriate Timeouts

```ini
[preScripts]
timeout = 10m  # Adjust based on script complexity

[postScripts]
timeout = 15m  # Allow time for migrations
```

### 4. Implement Retry Logic

```bash
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if check_condition; then
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 2
done
```

### 5. Provide Detailed Logging

```bash
echo "=== Starting backup process ==="
echo "Backup directory: $BACKUP_DIR"
echo "Timestamp: $(date)"
echo "Container: $CAPTN_CONTAINER_NAME"
```

### 6. Handle Errors Gracefully

```bash
set -e  # Exit on error
trap 'echo "Error on line $LINENO"; exit 1' ERR

# Perform operations with error checking
if ! perform_backup; then
    echo "Error: Backup failed"
    exit 1
fi
```

### 7. Test Scripts Manually

```bash
# Test script manually before using with captn
export CAPTN_CONTAINER_NAME=postgres
export CAPTN_SCRIPT_TYPE=pre
export CAPTN_DRY_RUN=true
export CAPTN_LOG_LEVEL=INFO
export CAPTN_CONFIG_DIR=/app/conf
export CAPTN_SCRIPTS_DIR=/app/conf/scripts

./postgres_pre.sh
```

### 8. Use Container-Specific Scripts

Create container-specific scripts for services with unique requirements:

```bash
# Generic script for all containers
/app/conf/scripts/pre.sh

# Specific script for PostgreSQL
/app/conf/scripts/PostgreSQL_pre.sh

# Specific script for Redis
/app/conf/scripts/redis_pre.sh
```

### 9. Keep Scripts Simple

- Focus on a single responsibility
- Avoid complex logic
- Use external tools when appropriate
- Document the purpose clearly

### 10. Secure Sensitive Data

```bash
# Use environment variables for secrets
DB_PASSWORD="${DB_PASSWORD:-}"

# Never log sensitive information
echo "Connecting to database..." # Don't log password
```

---

## Troubleshooting

### Script Not Executing

**Check if scripts are enabled:**
```ini
[preScripts]
enabled = true

[postScripts]
enabled = true
```

**Verify script exists and is named correctly:**
```bash
ls -la /app/conf/scripts/
# Should show: container_name_pre.sh or pre.sh
```

**Check execute permissions:**
```bash
chmod +x /app/conf/scripts/*.sh
```

### Script Timeout

**Increase timeout in configuration:**
```ini
[preScripts]
timeout = 20m  # Increase from default 5m

[postScripts]
timeout = 20m
```

**Optimize script:**
- Remove unnecessary operations
- Parallelize where possible
- Reduce retry delays

### Script Fails in Dry-Run

**Ensure dry-run handling:**
```bash
if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would perform actions..."
    exit 0  # Exit early in dry-run
fi

# Actual operations below
```

### Script Works Manually but Fails in captn

**Check environment:**
```bash
# captn provides specific environment variables
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Config Dir: $CAPTN_CONFIG_DIR"
```

**Verify paths:**
```bash
# Use absolute paths
BACKUP_DIR="/var/backups/myapp"

# Or use provided variables
BACKUP_DIR="$CAPTN_CONFIG_DIR/backups"
```

### Debugging Scripts

**Enable debug logging:**
```bash
docker exec captn captn --log-level debug --filter name=yourcontainer
```

**Add debug output to script:**
```bash
#!/bin/bash
set -x  # Print commands as they execute

echo "=== Debug Information ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"
env | grep CAPTN_  # Print all captn variables
```

**Test script manually:**
```bash
# Set environment variables
export CAPTN_CONTAINER_NAME=mycontainer
export CAPTN_SCRIPT_TYPE=pre
export CAPTN_DRY_RUN=false

# Run script
/app/conf/scripts/mycontainer_pre.sh
```

### Container Not Found Errors

**Verify container name:**
```bash
# List all containers
docker ps -a --format "{{.Names}}"

# Check if name matches
docker ps --format "{{.Names}}" | grep "^${CAPTN_CONTAINER_NAME}$"
```

**Handle container name variations:**
```bash
# Flexible matching
CONTAINER_PATTERN="${CAPTN_CONTAINER_NAME}"
if docker ps --format "{{.Names}}" | grep -qi "$CONTAINER_PATTERN"; then
    echo "Container found"
fi
```

---

## Quick Reference

### Script Template

```bash
#!/bin/bash
set -e

echo "=== Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"

if [ "$CAPTN_DRY_RUN" = "true" ]; then
    echo "Would perform actions..."
    exit 0
fi

# Verify container is running
if ! docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
    echo "Error: Container not running"
    exit 1
fi

# Your logic here
echo "Performing actions..."

echo "=== Script Completed ==="
exit 0
```

### Common Commands

```bash
# Check container exists
docker ps -a --filter "name=^${CAPTN_CONTAINER_NAME}$"

# Check container is running
docker ps --filter "name=^${CAPTN_CONTAINER_NAME}$"

# Execute command in container
docker exec "$CAPTN_CONTAINER_NAME" command

# Pause container
docker pause "$CAPTN_CONTAINER_NAME"

# Unpause container
docker unpause "$CAPTN_CONTAINER_NAME"

# Get container logs
docker logs "$CAPTN_CONTAINER_NAME"

# Inspect container
docker inspect "$CAPTN_CONTAINER_NAME"
```

---

**Previous:** [← Configuration Guide](03-Configuration.md)

**Home:** [← Introduction](01-Introduction.md)

