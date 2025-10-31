# CLI Reference

This document provides a complete reference for the captn command-line interface (CLI).

## Table of Contents

- [CLI Reference](#cli-reference)
  - [Table of Contents](#table-of-contents)
  - [Basic Usage](#basic-usage)
  - [Command Syntax](#command-syntax)
  - [Options](#options)
    - [`--version`, `-v`](#--version--v)
    - [`--run`, `-r`](#--run--r)
    - [`--dry-run`, `-t`](#--dry-run--t)
    - [`--filter`](#--filter)
    - [`--log-level`, `-l`](#--log-level--l)
    - [`--clear-logs`, `-c`](#--clear-logs--c)
    - [`--daemon`, `-d`](#--daemon--d)
  - [Filters](#filters)
    - [Name Filters](#name-filters)
    - [Multiple Name Filters](#multiple-name-filters)
  - [Examples](#examples)
    - [Basic Operations](#basic-operations)
    - [Filtering Examples](#filtering-examples)
    - [Logging Examples](#logging-examples)
    - [Combined Examples](#combined-examples)
    - [Testing and Troubleshooting](#testing-and-troubleshooting)
  - [Exit Codes](#exit-codes)
  - [Environment Variables](#environment-variables)
    - [`TZ`](#tz)
    - [Docker Socket](#docker-socket)
  - [Best Practices](#best-practices)
    - [1. Always Test with Dry-Run](#1-always-test-with-dry-run)
    - [2. Use Filters Strategically](#2-use-filters-strategically)
    - [3. Monitor with Debug Logging](#3-monitor-with-debug-logging)
    - [4. Clear Logs for Debugging](#4-clear-logs-for-debugging)
    - [5. Schedule Updates Appropriately](#5-schedule-updates-appropriately)
  - [Troubleshooting](#troubleshooting)
    - [Container Update Failed](#container-update-failed)
  - [Quick Reference Card](#quick-reference-card)

## Basic Usage

The basic syntax for running captn:

```bash
captn [OPTIONS]
```

When running captn inside a Docker container:

```bash
docker exec captn captn [OPTIONS]
```

## Command Syntax

```
captn [--version] [--run] [--dry-run] [--filter FILTER [FILTER ...]]
      [--log-level {debug,info,warning,error,critical}]
      [--clear-logs] [--daemon]
```

## Options

### `--version`, `-v`

Display the current version of captn and exit.

**Usage:**
```bash
captn --version
captn -v
```

**Example Output:**
```
0.7.19
```

---

### `--run`, `-r`

Force actual execution without dry-run mode, overriding the configuration file setting.

**Usage:**
```bash
captn --run
captn -r
```

**Details:**
- Overrides the `dryRun` setting in the configuration file
- Useful when `dryRun = true` is set in config but you want to run actual updates
- Takes precedence over both config file and `--dry-run` flag

**Example:**
```bash
# Configuration has dryRun = true
# Force actual execution:
captn --run
```

---

### `--dry-run`, `-t`

Run captn in dry-run mode to preview what it would do without making actual changes.

**Usage:**
```bash
captn --dry-run
captn -t
```

**Details:**
- No actual changes are made to containers or images
- Shows what updates would be applied
- Useful for testing configuration changes
- Helps understand update behavior before applying
- All logs are marked with `[DRY_RUN]`

**Example:**
```bash
# Preview updates for all containers
captn --dry-run

# Preview updates for specific container
captn --dry-run --filter name=nginx
```

**Output Example:**
```
2025-01-15 10:30:15 INFO     [DRY_RUN] Processing container 'nginx'
2025-01-15 10:30:16 INFO     [DRY_RUN] Would process patch update for 'nginx' (1.21.0 -> 1.21.1)
2025-01-15 10:30:16 INFO     [DRY_RUN] Would pull new image: nginx:1.21.1
2025-01-15 10:30:16 INFO     [DRY_RUN] Would recreate container 'nginx' with updated image
```

---

### `--filter`

Filter the list of containers to process based on container names.

**Usage:**
```bash
captn --filter name=<pattern> [name=<pattern> ...]
```

**Supported Filter Types:**
- `name=<container_name>`: Filter by container name

**Details:**
- Multiple name filters can be specified
- Multiple name filters are combined with OR logic
- See [Filters](#filters) section for detailed information

**Examples:**
```bash
# Single name filter
captn --filter name=nginx

# Multiple name filters (OR logic)
captn --filter name=nginx name=redis

# Wildcard patterns
captn --filter name=web-* name=api-*
```

---

### `--log-level`, `-l`

Set the logging verbosity level.

**Usage:**
```bash
captn --log-level LEVEL
captn -l LEVEL
```

**Valid Levels:**
- `debug`: Most verbose, shows all details including function calls
- `info`: Standard information level (recommended, default)
- `warning`: Only warnings and errors
- `error`: Only errors
- `critical`: Only critical errors

**Details:**
- Overrides the `level` setting in `[logging]` section of config
- Affects both console and file logging
- DEBUG level includes file locations and function names
- DEBUG level increases log file size and rotation settings

**Examples:**
```bash
# Standard operation (default)
captn --log-level info

# Detailed debugging
captn --log-level debug

# Only errors
captn --log-level error

# Using short form
captn -l debug
```

**Debug Output Example:**
```
2025-01-15 10:30:15 DEBUG    [app.__main__.main]                          Processing container 'nginx'
2025-01-15 10:30:15 DEBUG    [app.utils.engines.docker.get_containers]    Found 5 containers
```

**Info Output Example:**
```
2025-01-15 10:30:15 INFO     Processing container 'nginx'
2025-01-15 10:30:16 INFO     Processing patch update for 'nginx' (1.21.0 -> 1.21.1)
```

---

### `--clear-logs`, `-c`

Delete all log files before starting the update process.

**Usage:**
```bash
captn --clear-logs
captn -c
```

**Details:**
- Removes all `captn.log*` files from the logs directory
- Removes all `container_comparison_*.json` files
- Useful for starting fresh log analysis
- Deleted files are reported in the log output
- Can be combined with other options

**Files Deleted:**
- `captn.log` - Current log file
- `captn.log.1`, `captn.log.2`, etc. - Rotated log files
- `container_comparison_*.json` - Container comparison files

**Examples:**
```bash
# Clear logs and run updates
captn --clear-logs

# Clear logs and do dry-run
captn --clear-logs --dry-run

# Clear logs with debug level
captn --clear-logs --log-level debug
```

**Output:**
```
2025-01-15 10:30:15 INFO     Deleted log file: captn.log
2025-01-15 10:30:15 INFO     Deleted log file: captn.log.1
2025-01-15 10:30:15 INFO     Deleted comparison file: container_comparison_nginx_20250115_103015.json
2025-01-15 10:30:15 INFO     Successfully deleted 3 file(s)
```

---

### `--daemon`, `-d`

Run captn as a daemon with scheduled execution based on the `cronSchedule` configuration.

**Usage:**
```bash
captn --daemon
captn -d
```

**Details:**
- **Note:** This parameter is used by default in the captn Docker image and typically does not need to be specified manually by users
- Runs continuously in the foreground
- Executes updates according to `cronSchedule` in configuration
- Handles graceful shutdown on SIGTERM and SIGINT signals
- The official captn Docker image is pre-configured to run in daemon mode
- Only needs to be specified explicitly when running captn outside of the container or for manual execution

**Configuration:**
```ini
[general]
cronSchedule = 30 2 * * *  # Daily at 2:30 AM
```

**Cron Schedule Format:**
```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
│ │ │ │ │
* * * * *
```

**Common Cron Schedules:**
```
30 2 * * *       # Daily at 2:30 AM
0 */6 * * *      # Every 6 hours
*/30 * * * *     # Every 30 minutes
0 2 * * 0        # Weekly on Sunday at 2:00 AM
0 2 1 * *        # Monthly on the 1st at 2:00 AM
```

**Docker Usage:**
```bash
# Run captn in Docker (daemon mode is default)
docker run -d \
  --name captn \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v ~/captn/conf:/app/conf \
  -v ~/captn/logs:/app/logs \
  captnio/captn:0.8.2
```

**Note:** The captn Docker image runs in daemon mode by default. The `--daemon` flag is already configured internally and does not need to be specified.

**Output:**
```
2025-01-15 10:30:15 INFO     Starting captn scheduler
2025-01-15 10:30:15 INFO     Cron schedule: 30 2 * * *
2025-01-15 10:30:15 INFO     Next run: 2025-01-16 02:30:00
2025-01-15 10:30:15 INFO     Scheduler started, waiting for scheduled execution...
```

---

## Filters

Filters allow you to selectively process only certain containers. Multiple filters can be combined to create complex selection criteria.

### Name Filters

Filter containers by their name.

**Syntax:**
```bash
--filter name=<pattern>
```

**Pattern Matching:**
- **Exact match**: No wildcards → exact name match
  - `name=nginx` matches only "nginx"
- **Pattern match**: With wildcards → pattern matching
  - `*` matches zero or more characters
  - `?` matches exactly one character
  - `[abc]` matches any character in the brackets

**Examples:**

**Exact Name Match:**
```bash
# Match only container named "nginx"
captn --filter name=nginx
```

**Wildcard Patterns:**
```bash
# Match all containers starting with "web-"
captn --filter name=web-*

# Match all containers ending with "-api"
captn --filter name=*-api

# Match containers containing "cloud"
captn --filter name=*cloud*

# Match specific pattern (e.g., cloud-01, cloud-02)
captn --filter name=cloud-0?

# Match using character class
captn --filter name=web-[123]
```

**Multiple Name Filters (OR Logic):**
```bash
# Match nginx OR redis OR postgres
captn --filter name=nginx name=redis name=postgres

# Match web-* OR api-* containers
captn --filter name=web-* name=api-*

# Complex pattern combination
captn --filter name=prod-* name=staging-* name=dev-*
```

### Multiple Name Filters

Multiple name filters can be combined using OR logic to select different containers.

**Logic:**
- Multiple `name` filters are combined with **OR** logic
- A container is selected if it matches **any** of the name patterns

**Examples:**

```bash
# Match nginx OR redis OR postgres
captn --filter name=nginx name=redis name=postgres

# Match web-* OR api-* containers
captn --filter name=web-* name=api-*

# Match multiple production patterns
captn --filter name=prod-web-* name=prod-api-* name=prod-db-*
```

**Complex Example:**
```bash
# Process production web and api containers
captn --filter name=prod-web-* name=prod-api-*

# This matches:
# ✓ prod-web-1
# ✓ prod-web-2
# ✓ prod-api-1
# ✗ dev-web-1 (wrong name)
# ✗ prod-db-1 (wrong name)
```

---

## Examples

### Basic Operations

**Check Version:**
```bash
captn --version
```

**Dry-Run (Preview Changes):**
```bash
captn --dry-run
```

**Run Actual Updates:**
```bash
captn --run
```

### Filtering Examples

**Update Single Container:**
```bash
captn --filter name=nginx
```

**Update Multiple Specific Containers:**
```bash
captn --filter name=nginx name=redis name=postgres
```

**Update All Production Containers:**
```bash
captn --filter name=prod-*
```

**Update Web and API Containers:**
```bash
captn --filter name=web-* name=api-*
```

### Logging Examples

**Standard Logging:**
```bash
captn --log-level info
```

**Debug Mode:**
```bash
captn --log-level debug --filter name=nginx
```

**Clear Logs Before Run:**
```bash
captn --clear-logs --log-level debug
```

### Combined Examples

**Dry-Run with Debug Logging:**
```bash
captn --dry-run --log-level debug
```

**Clear Logs and Run Updates:**
```bash
captn --clear-logs --run
```

**Update Specific Containers with Debug:**
```bash
captn --filter name=prod-* --log-level debug
```

**Dry-Run for Production Containers:**
```bash
captn --dry-run --filter name=prod-* --log-level info
```

**Force Run with Specific Container:**
```bash
captn --run --filter name=nginx --clear-logs
```

### Testing and Troubleshooting

**Test Configuration:**
```bash
# Preview what would happen
captn --dry-run --log-level debug
```

**Test Specific Container:**
```bash
# Debug single container updates
captn --dry-run --filter name=nginx --log-level debug
```

**Test with Fresh Logs:**
```bash
# Clear old logs and test
captn --clear-logs --dry-run --log-level debug
```

**Verbose Update:**
```bash
# Run with maximum logging
captn --run --log-level debug --clear-logs
```

---

## Exit Codes

captn uses standard Unix exit codes:

| Code | Meaning                                         |
| ---- | ----------------------------------------------- |
| 0    | Success - All operations completed successfully |
| 1    | Error - General error occurred during execution |

**Note:** Exit codes are only relevant for non-daemon mode. In daemon mode, captn runs continuously and doesn't exit unless stopped or an unrecoverable error occurs.

---

## Environment Variables

captn respects the following environment variables:

### `TZ`

Set the timezone for log timestamps and scheduled execution.

**Example:**
```bash
docker run -d \
  --name captn \
  -e TZ=Europe/Berlin \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v ~/captn/conf:/app/conf \
  captnio/captn:0.8.2
```

### Docker Socket

captn requires access to the Docker socket to manage containers.

**Default:** `/var/run/docker.sock`

**Example:**
```bash
docker run -d \
  --name captn \
  -v /var/run/docker.sock:/var/run/docker.sock \
  captnio/captn:0.8.2
```

---

## Best Practices

### 1. Always Test with Dry-Run

Before applying updates, especially in production:

```bash
# Test configuration
captn --dry-run

# Test specific containers
captn --dry-run --filter name=prod-*

# Test with debug output
captn --dry-run --log-level debug
```

### 2. Use Filters Strategically

Start with specific filters and expand gradually:

```bash
# Start with single container
captn --dry-run --filter name=test-nginx

# Expand to group
captn --dry-run --filter name=test-*

# Eventually apply to multiple containers
captn --run --filter name=prod-*
```

### 3. Monitor with Debug Logging

Use debug logging to understand behavior:

```bash
captn --log-level debug --filter name=problematic-container
```

### 4. Clear Logs for Debugging

Start with fresh logs when troubleshooting:

```bash
captn --clear-logs --log-level debug --dry-run
```

### 5. Schedule Updates Appropriately

Set cron schedules during low-traffic periods:

```ini
[general]
# Run at 3 AM daily (low traffic)
cronSchedule = 0 3 * * *

# Or weekly on Sunday at 2 AM
cronSchedule = 0 2 * * 0
```

---

## Troubleshooting

### Container Update Failed

**Check logs:**
```bash
# View detailed logs
docker logs captn

# Or check log files
tail ~/captn/logs/captn.log
```

**Debug specific container by trying it again with a cleared log file:**
```bash
captn --clear-logs --log-level debug --filter name=failed-container
```

---

## Quick Reference Card

```bash
# Version
captn --version

# Dry-run (preview)
captn --dry-run

# Actual run
captn --run

# Filter by name
captn --filter name=nginx

# Multiple name filters
captn --filter name=web-* name=api-*

# Debug logging
captn --log-level debug

# Clear logs
captn --clear-logs

# Common combinations
captn --dry-run --log-level debug --filter name=nginx
captn --run --filter name=prod-* --log-level info
captn --clear-logs --dry-run --log-level debug
captn --filter name=web-* name=api-* --log-level debug
```

---

**Next:** [Configuration Guide →](03-Configuration.md)

**Previous:** [← Introduction](01-Introduction.md)

