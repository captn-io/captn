# Configuration Reference

This document provides a comprehensive reference for all captn configuration options.

## Table of Contents

- [Configuration File](#configuration-file)
- [File Format](#file-format)
- [Configuration Sections](#configuration-sections)
  - [general](#general)
  - [logging](#logging)
  - [update](#update)
  - [updateVerification](#updateverification)
  - [prune](#prune)
  - [selfUpdate](#selfupdate)
  - [preScripts](#prescripts)
  - [postScripts](#postscripts)
  - [docker](#docker)
  - [ghcr](#ghcr)
  - [registryAuth](#registryauth)
  - [envFiltering](#envfiltering)
  - [notifiers](#notifiers)
  - [notifiers.telegram](#notifierstelegram)
  - [notifiers.email](#notifiersemail)
  - [assignmentsByName](#assignmentsbyname)
  - [rules](#rules)
- [Built-in Rules](#built-in-rules)
- [Custom Rules](#custom-rules)
- [Rule Properties](#rule-properties)
- [Complete Example](#complete-example)

---

## Configuration File

### Location

**Default:** `/app/conf/captn.cfg`

When running in Docker:
- Mount configuration directory: `-v ~/captn/conf:/app/conf`
- Configuration file: `~/captn/conf/captn.cfg`
- Example file: `~/captn/conf/captn.example.cfg` (auto-generated)

### Creating Configuration

1. An example configuration is automatically created at `/app/conf/captn.example.cfg`
2. Copy the example to create your configuration:
   ```bash
   cp ~/captn/conf/captn.example.cfg ~/captn/conf/captn.cfg
   ```
3. Edit the configuration file to match your needs

---

## File Format

The configuration file uses the INI format:

```ini
[section]
key = value
```

### Data Types

- **Boolean**: `true` or `false` (lowercase)
- **String**: Plain text
- **Integer**: Numeric values without decimals
- **Duration**: Number + unit (`30s`, `2m`, `1h`, `24h`, `7d`)
- **JSON**: JSON objects or arrays (for rules and complex structures)

### Duration Format

Durations use the format: `<number><unit>`

**Units:**
- `s` = seconds
- `m` = minutes
- `h` = hours
- `d` = days

**Examples:**
- `30s` = 30 seconds
- `5m` = 5 minutes
- `2h` = 2 hours
- `24h` = 24 hours
- `7d` = 7 days

### Comments

Lines starting with `#` are comments:

```ini
# This is a comment
[section]
# This setting controls...
key = value
```

---

## Configuration Sections

### `[general]`

General application settings.

#### `dryRun`

Enable dry-run mode (no actual updates will be performed).

- **Type:** Boolean
- **Default:** `false`
- **Values:** `true`, `false`

**Example:**
```ini
[general]
dryRun = false
```

**Note:** Can be overridden by `--dry-run` or `--run` command-line flags.

#### `cronSchedule`

Cron schedule for automatic updates when running in daemon mode.

- **Type:** String (cron expression)
- **Default:** `30 2 * * *` (daily at 2:30 AM)
- **Format:** `minute hour day month weekday`

**Cron Format:**
```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday = 0)
│ │ │ │ │
* * * * *
```

**Examples:**
```ini
# Daily at 2:30 AM
cronSchedule = 30 2 * * *

# Every 6 hours
cronSchedule = 0 */6 * * *

# Every 30 minutes
cronSchedule = */30 * * * *

# Weekly on Sunday at 2:00 AM
cronSchedule = 0 2 * * 0

# Monthly on the 1st at 3:00 AM
cronSchedule = 0 3 1 * *
```

---

### `[logging]`

Logging configuration.

#### `level`

Logging verbosity level.

- **Type:** String
- **Default:** `INFO`
- **Values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Descriptions:**
- `DEBUG`: Most verbose, shows all details including function calls
- `INFO`: Standard operational information (recommended)
- `WARNING`: Only warnings and errors
- `ERROR`: Only error conditions
- `CRITICAL`: Only critical failures

**Example:**
```ini
[logging]
level = INFO
```

**Note:** Can be overridden by `--log-level` command-line flag.

---

### `[update]`

Container update settings.

#### `delayBetweenUpdates`

Delay between processing updates for the same container (progressive upgrades).

- **Type:** Duration
- **Default:** `2m`
- **Minimum:** `1s`

**Purpose:** Prevents overwhelming the system and allows time for verification between progressive updates.

**Example:**
```ini
[update]
delayBetweenUpdates = 2m
```

**Note:** Only applies when progressive upgrades are enabled in the rule and multiple versions are being applied.

---

### `[updateVerification]`

Settings for verifying container stability after updates.

#### `maxWait`

Maximum time to wait for a container to become stable after update.

- **Type:** Duration
- **Default:** `480s` (8 minutes)
- **Minimum:** `10s`

**Example:**
```ini
[updateVerification]
maxWait = 480s
```

#### `stableTime`

Time a container must remain in a healthy state before considering the update successful.

- **Type:** Duration
- **Default:** `15s`
- **Minimum:** `5s`

**Example:**
```ini
[updateVerification]
stableTime = 15s
```

#### `checkInterval`

Interval between stability checks during update verification.

- **Type:** Duration
- **Default:** `5s`
- **Minimum:** `1s`

**Example:**
```ini
[updateVerification]
checkInterval = 5s
```

#### `gracePeriod`

Additional time to wait after container becomes stable before proceeding.

- **Type:** Duration
- **Default:** `15s`
- **Minimum:** `0s`

**Purpose:** Provides a buffer to catch any late failures after initial stability.

**Example:**
```ini
[updateVerification]
gracePeriod = 15s
```

**Complete Example:**
```ini
[updateVerification]
maxWait = 480s        # Wait up to 8 minutes
stableTime = 15s      # Must be stable for 15 seconds
checkInterval = 5s    # Check every 5 seconds
gracePeriod = 15s     # Wait additional 15 seconds after stable
```

---

### `[prune]`

Cleanup settings for images and containers.

#### `removeUnusedImages`

Remove unused Docker images after successful updates.

- **Type:** Boolean
- **Default:** `false`
- **Values:** `true`, `false`

**Example:**
```ini
[prune]
removeUnusedImages = false
```

**Note:** Images are only removed if they are not being used by any container.

#### `removeOldContainers`

Remove old backup containers after successful updates.

- **Type:** Boolean
- **Default:** `true`
- **Values:** `true`, `false`

**Example:**
```ini
[prune]
removeOldContainers = true
```

**Backup Container Identification:**
Backup containers are identified by:
- Container name contains `_bak_cu_` (backup container-updater)
- Container status is "exited"
- Container name ends with timestamp: `YYYYMMDD-HHMMSS`

**Example backup name:** `nginx_bak_cu_20250115_143022`

#### `minBackupAge`

Minimum age a backup container must reach before it can be deleted.

- **Type:** Duration
- **Default:** `48h`
- **Minimum:** `0s` (immediate deletion allowed)

**Example:**
```ini
[prune]
minBackupAge = 48h
```

#### `minBackupsToKeep`

Minimum number of backup containers to keep for each container.

- **Type:** Integer
- **Default:** `1`
- **Minimum:** `0` (no backups kept)

**Example:**
```ini
[prune]
minBackupsToKeep = 1
```

**Complete Example:**
```ini
[prune]
removeUnusedImages = true
removeOldContainers = true
minBackupAge = 48h
minBackupsToKeep = 2
```

**Cleanup Logic:**
- Backups younger than `minBackupAge` are always kept
- At least `minBackupsToKeep` backups are kept per container
- Older backups beyond `minBackupsToKeep` are removed

---

### `[selfUpdate]`

Settings for captn self-update functionality.

#### `removeHelperContainer`

Remove helper containers after successful self-updates.

- **Type:** Boolean
- **Default:** `true`
- **Values:** `true`, `false`

**Purpose:** Helper containers are temporary containers created to perform the actual update of the captn container itself.

**Example:**
```ini
[selfUpdate]
removeHelperContainer = true
```

**Options:**
- `true`: Helper container is automatically removed after completion (recommended)
- `false`: Helper container remains for manual inspection (debugging)

---

### `[preScripts]`

Configuration for pre-update script execution.

#### `enabled`

Enable pre-update script execution.

- **Type:** Boolean
- **Default:** `true`
- **Values:** `true`, `false`

**Example:**
```ini
[preScripts]
enabled = true
```

#### `scriptsDirectory`

Directory containing pre-update scripts.

- **Type:** String (path)
- **Default:** `/app/conf/scripts`

**Example:**
```ini
[preScripts]
scriptsDirectory = /app/conf/scripts
```

**Note:** When running in Docker, mount this directory: `-v ~/captn/conf/scripts:/app/conf/scripts`

#### `timeout`

Maximum time allowed for pre-script execution.

- **Type:** Duration
- **Default:** `5m`
- **Minimum:** `0s`

**Example:**
```ini
[preScripts]
timeout = 5m
```

**Note:** If a script doesn't complete within this time, it will be terminated.

#### `continueOnFailure`

Whether to continue with the update if pre-script fails.

- **Type:** Boolean
- **Default:** `false`
- **Values:** `true`, `false`

**Example:**
```ini
[preScripts]
continueOnFailure = false
```

**Options:**
- `false`: Abort update if pre-script fails (recommended)
- `true`: Continue with update even if pre-script fails

**Complete Example:**
```ini
[preScripts]
enabled = true
scriptsDirectory = /app/conf/scripts
timeout = 10m
continueOnFailure = false
```

---

### `[postScripts]`

Configuration for post-update script execution.

#### `enabled`

Enable post-update script execution.

- **Type:** Boolean
- **Default:** `true`
- **Values:** `true`, `false`

**Example:**
```ini
[postScripts]
enabled = true
```

#### `scriptsDirectory`

Directory containing post-update scripts.

- **Type:** String (path)
- **Default:** `/app/conf/scripts`

**Example:**
```ini
[postScripts]
scriptsDirectory = /app/conf/scripts
```

#### `timeout`

Maximum time allowed for post-script execution.

- **Type:** Duration
- **Default:** `5m`
- **Minimum:** `0s`

**Example:**
```ini
[postScripts]
timeout = 5m
```

#### `rollbackOnFailure`

Whether to rollback the container if post-script fails.

- **Type:** Boolean
- **Default:** `true`
- **Values:** `true`, `false`

**Example:**
```ini
[postScripts]
rollbackOnFailure = true
```

**Options:**
- `true`: Rollback to previous version if post-script fails (recommended)
- `false`: Keep updated version even if post-script fails

**Complete Example:**
```ini
[postScripts]
enabled = true
scriptsDirectory = /app/conf/scripts
timeout = 10m
rollbackOnFailure = true
```

---

### `[docker]`

Docker Hub registry configuration.

#### `apiUrl`

Docker Hub API URL for fetching image metadata.

- **Type:** String (URL)
- **Default:** `https://registry.hub.docker.com/v2`

**Example:**
```ini
[docker]
apiUrl = https://registry.hub.docker.com/v2
```

**Note:** Usually doesn't need to be changed unless using a custom registry.

#### `pageCrawlLimit`

Maximum number of pages to crawl when searching for images.

- **Type:** Integer
- **Default:** `1000`
- **Range:** `1` - `1000`

**Example:**
```ini
[docker]
pageCrawlLimit = 1000
```

**Note:** Higher values allow finding older images but increase API usage.

#### `pageSize`

Number of images to fetch per API request.

- **Type:** Integer
- **Default:** `100`
- **Range:** `1` - `100`

**Example:**
```ini
[docker]
pageSize = 100
```

**Note:** Higher values reduce API calls but increase memory usage.

**Complete Example:**
```ini
[docker]
apiUrl = https://registry.hub.docker.com/v2
pageCrawlLimit = 1000
pageSize = 100
```

---

### `[ghcr]`

GitHub Container Registry configuration.

#### `apiUrl`

GHCR API URL for fetching image metadata.

- **Type:** String (URL)
- **Default:** `https://ghcr.io/v2`

**Example:**
```ini
[ghcr]
apiUrl = https://ghcr.io/v2
```

#### `pageCrawlLimit`

Maximum number of pages to crawl when searching for images.

- **Type:** Integer
- **Default:** `1000`
- **Range:** `1` - `1000`

**Example:**
```ini
[ghcr]
pageCrawlLimit = 1000
```

#### `pageSize`

Number of images to fetch per API request.

- **Type:** Integer
- **Default:** `100`
- **Range:** `1` - `100`

**Example:**
```ini
[ghcr]
pageSize = 100
```

**Complete Example:**
```ini
[ghcr]
apiUrl = https://ghcr.io/v2
pageCrawlLimit = 1000
pageSize = 100
```

---

### `[registryAuth]`

Registry authentication configuration for private repositories.

#### `enabled`

Enable registry authentication.

- **Type:** Boolean
- **Default:** `false`
- **Values:** `true`, `false`

**Example:**
```ini
[registryAuth]
enabled = false
```

#### `credentialsFile`

Path to JSON file containing registry credentials.

- **Type:** String (path)
- **Default:** `/app/conf/registry-credentials.json`

**Example:**
```ini
[registryAuth]
credentialsFile = /app/conf/registry-credentials.json
```

**Credentials File Format:**
```json
{
    "registries": {
        "https://registry.hub.docker.com/v2": {
            "username": "your_dockerhub_username",
            "password": "your_dockerhub_password_or_token"
        },
        "https://ghcr.io/v2": {
            "token": "your_github_personal_access_token"
        }
    },
    "repositories": {
        "captnio/captn": {
            "username": "captnio",
            "password": "specific_token_for_captn"
        },
        "myorg/private-repo": {
            "token": "specific_token_for_private_repo"
        }
    }
}
```

**Structure:**
- `registries`: Registry-level credentials (apply to all images from that registry)
- `repositories`: Repository-specific credentials (override registry-level credentials)

**Authentication Priority:**
1. Repository-specific credentials (if defined)
2. Registry-level credentials (if defined)
3. No authentication

**Complete Example:**
```ini
[registryAuth]
enabled = true
credentialsFile = /app/conf/registry-credentials.json
```

---

### `[envFiltering]`

Environment variable filtering during container recreation.

#### `enabled`

Enable environment variable filtering.

- **Type:** Boolean
- **Default:** `true`
- **Values:** `true`, `false`

**Purpose:** Filters out environment variables from the image that shouldn't be preserved during updates.

**Example:**
```ini
[envFiltering]
enabled = true
```

#### `excludePatterns`

Patterns for environment variables to exclude from container recreation.

- **Type:** JSON array of strings
- **Default:** `[]` (empty array)
- **Supports:** Wildcards (`*`, `?`, `[]`)

**Example:**
```ini
[envFiltering]
excludePatterns = [
    "IMMICH_BUILD_*",
    "NODE_VERSION",
    "BUILD_*",
    "GIT_*"
]
```

**Note:** These variables are typically build-time variables that shouldn't be preserved.

#### `preservePatterns`

Patterns for environment variables to always preserve.

- **Type:** JSON array of strings
- **Default:** `[]` (empty array)
- **Supports:** Wildcards (`*`, `?`, `[]`)

**Example:**
```ini
[envFiltering]
preservePatterns = [
    "TZ",
    "PUID",
    "PGID",
    "UMASK",
    "DB_*",
    "REDIS_*"
]
```

#### `containerSpecificRules`

Container-specific environment variable filtering rules.

- **Type:** JSON object
- **Default:** `{}` (empty object)

**Format:**
```json
{
    "container_name": {
        "excludePatterns": ["PATTERN1", "PATTERN2"],
        "preservePatterns": ["PATTERN3", "PATTERN4"]
    }
}
```

**Example:**
```ini
[envFiltering]
containerSpecificRules = {
    "immich": {
        "excludePatterns": [
            "IMMICH_BUILD_*",
            "IMMICH_SOURCE_*",
            "IMMICH_REPOSITORY_*"
        ],
        "preservePatterns": [
            "IMMICH_ENV",
            "IMMICH_LOG_LEVEL",
            "IMMICH_MACHINE_LEARNING_URL"
        ]
    },
    "nextcloud": {
        "excludePatterns": [
            "NC_BUILD_*"
        ],
        "preservePatterns": [
            "NC_*",
            "NEXTCLOUD_*"
        ]
    }
}
```

**Matching Logic:**
- Container names are matched using case-insensitive substring matching
- Example: `"immich"` matches `"immich-server"`, `"immich-api"`, etc.
- Container-specific rules override global patterns

**Complete Example:**
```ini
[envFiltering]
enabled = true
excludePatterns = [
    "BUILD_*",
    "GIT_*"
]
preservePatterns = [
    "TZ",
    "PUID",
    "PGID"
]
containerSpecificRules = {
    "immich": {
        "excludePatterns": [
            "IMMICH_BUILD_*"
        ],
        "preservePatterns": [
            "IMMICH_ENV"
        ]
    }
}
```

---

### `[notifiers]`

Global notification settings.

#### `enabled`

Enable/disable all notifications globally.

- **Type:** Boolean
- **Default:** `false`
- **Values:** `true`, `false`

**Example:**
```ini
[notifiers]
enabled = false
```

**Note:** Even if individual notifiers are enabled, they won't work if this is `false`.

---

### `[notifiers.telegram]`

Telegram notification configuration.

#### `enabled`

Enable Telegram notifications.

- **Type:** Boolean
- **Default:** `false`
- **Values:** `true`, `false`

**Example:**
```ini
[notifiers.telegram]
enabled = false
```

#### `token`

Telegram bot token from @BotFather.

- **Type:** String
- **Required if enabled**

**Example:**
```ini
[notifiers.telegram]
token = 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

**How to get:**
1. Message @BotFather on Telegram
2. Create a new bot with `/newbot`
3. Copy the token provided

#### `chatId`

Telegram chat ID (user or group).

- **Type:** String or Integer
- **Required if enabled**

**Example:**
```ini
[notifiers.telegram]
chatId = 123456789
```

**How to get:**
1. For user: Message @userinfobot on Telegram
2. For group: Add @userinfobot to your group

**Complete Example:**
```ini
[notifiers.telegram]
enabled = true
token = 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
chatId = 123456789
```

---

### `[notifiers.email]`

Email notification configuration using SMTP.

#### `enabled`

Enable email notifications.

- **Type:** Boolean
- **Default:** `false`
- **Values:** `true`, `false`

**Example:**
```ini
[notifiers.email]
enabled = false
```

#### `smtpServer`

SMTP server address.

- **Type:** String
- **Required if enabled**

**Example:**
```ini
[notifiers.email]
smtpServer = smtp.gmail.com
```

#### `smtpPort`

SMTP server port.

- **Type:** Integer
- **Default:** `587`

**Example:**
```ini
[notifiers.email]
smtpPort = 587
```

#### `username`

SMTP username.

- **Type:** String
- **Required if enabled**

**Example:**
```ini
[notifiers.email]
username = your-email@gmail.com
```

#### `password`

SMTP password.

- **Type:** String
- **Required if enabled**

**Example:**
```ini
[notifiers.email]
password = your-app-password
```

#### `fromAddr`

Sender email address.

- **Type:** String
- **Required if enabled**

**Example:**
```ini
[notifiers.email]
fromAddr = captn@yourdomain.com
```

#### `toAddr`

Recipient email address.

- **Type:** String
- **Required if enabled**

**Example:**
```ini
[notifiers.email]
toAddr = admin@yourdomain.com
```

#### `timeout`

SMTP connection timeout in seconds.

- **Type:** Integer
- **Default:** `30`
- **Range:** 10-300 seconds

**Example:**
```ini
[notifiers.email]
timeout = 60
```

**Complete Example:**
```ini
[notifiers.email]
enabled = true
smtpServer = smtp.gmail.com
smtpPort = 587
username = your-email@gmail.com
password = your-app-password
fromAddr = captn@yourdomain.com
toAddr = admin@yourdomain.com
timeout = 60
```

#### Gmail Setup

To use Gmail as your SMTP server:

1. Enable 2-Factor Authentication on your Google account
2. Generate an App Password:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate a password for "Mail"
3. Use the App Password in the `password` field
4. Set `smtpServer = smtp.gmail.com` and `smtpPort = 587`

---

### `[assignmentsByName]`

Direct rule assignments by container name.

Assign specific update rules to containers by their name.

**Format:**
```ini
[assignmentsByName]
container_name = rule_name
```

**Example:**
```ini
[assignmentsByName]
# Databases: conservative updates
MariaDB = conservative
PostgreSQL = conservative
mysql-prod = conservative

# Web servers: patch-only
nginx = patch_only
apache = patch_only

# Caches: permissive
redis = permissive
memcached = permissive

# Development: permissive
dev-* = permissive
```

**Matching:**
- Exact name match (case-sensitive)
- If no match found, uses `default` rule
- Wildcards not supported in assignmentsByName

**Priority:**
1. Container label: `io.captn.rule=rule_name`
2. assignmentsByName match
3. Default rule

---

### `[rules]`

Rule definitions for update behavior.

Each rule is a JSON object defining update policies.

**Format:**
```ini
[rules]
rule_name = {JSON object}
```

**Example:**
```ini
[rules]
my_custom_rule = {
    "minImageAge": "3h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": true,
        "patch": true,
        "build": true,
        "digest": true,
        "scheme_change": false
    }
}
```

See [Built-in Rules](#built-in-rules) and [Custom Rules](#custom-rules) sections for detailed information.

---

## Built-in Rules

captn includes several pre-configured rules for common use cases.

### `default`

Conservative approach - no updates allowed by default (safety first).

```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": false,
    "allow": {
        "major": false,
        "minor": false,
        "patch": false,
        "build": false,
        "digest": false,
        "scheme_change": false
    }
}
```

**Use for:** Default safety, requires explicit rule assignment.

### `permissive`

Allows all update types - most permissive rule.

```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": true,
    "allow": {
        "major": true,
        "minor": true,
        "patch": true,
        "build": true,
        "digest": true,
        "scheme_change": false
    }
}
```

**Use for:** Development environments, non-critical services.

### `relaxed`

Allows major, minor, patch updates with conditions.

```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": true,
    "allow": {
        "major": true,
        "minor": true,
        "patch": true,
        "build": true,
        "digest": true,
        "scheme_change": false
    },
    "conditions": {
        "major": {
            "require": ["minor", "patch", "build"]
        }
    }
}
```

**Use for:** Staging environments, services with good testing.

**Note:** Major updates only if minor, patch, and build versions also exist.

### `strict`

Very conservative - no updates allowed (explicit approval required).

```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": false,
    "allow": {
        "major": false,
        "minor": false,
        "patch": false,
        "build": false,
        "digest": false,
        "scheme_change": false
    }
}
```

**Use for:** Critical production services requiring manual updates.

### `patch_only`

Only allows patch updates.

```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": false,
        "patch": true,
        "build": false,
        "digest": false,
        "scheme_change": false
    }
}
```

**Use for:** Production environments, stable services.

### `security_only`

Patch and digest updates (security focus).

```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": false,
        "patch": true,
        "build": false,
        "digest": true,
        "scheme_change": false
    }
}
```

**Use for:** Security-critical services.

### `digest_only`

Only digest updates (same tag, different image).

```json
{
    "minImageAge": "24h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": false,
        "patch": false,
        "build": false,
        "digest": true,
        "scheme_change": false
    }
}
```

**Use for:** Services using rolling tags (e.g., `latest`, `stable`).

### `ci_cd`

Minor, patch, and build updates.

```json
{
    "minImageAge": "3h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": true,
        "patch": true,
        "build": true,
        "digest": false,
        "scheme_change": false
    },
    "conditions": {
        "minor": {
            "require": ["patch"]
        }
    }
}
```

**Use for:** Development and CI/CD environments.

**Note:** Minor updates only if patch version also exists.

### `conservative`

Patch and build updates with longer image age.

```json
{
    "minImageAge": "24h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": false,
        "patch": true,
        "build": true,
        "digest": false,
        "scheme_change": false
    },
    "lagPolicy": {
        "major": 1
    }
}
```

**Use for:** Production services with cautious update approach.

**Note:** Stays 1 major version behind latest.

---

## Custom Rules

You can create custom rules tailored to your specific needs.

### Basic Custom Rule

```ini
[rules]
my_rule = {
    "minImageAge": "6h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": true,
        "patch": true,
        "build": true,
        "digest": true,
        "scheme_change": false
    }
}
```

### Rule with Conditions

```ini
[rules]
conditional_rule = {
    "minImageAge": "3h",
    "progressiveUpgrade": true,
    "allow": {
        "major": true,
        "minor": true,
        "patch": true,
        "build": true,
        "digest": true,
        "scheme_change": false
    },
    "conditions": {
        "major": {
            "require": ["minor", "patch", "build"]
        },
        "minor": {
            "require": ["patch"]
        }
    }
}
```

### Rule with Lag Policy

```ini
[rules]
lagging_rule = {
    "minImageAge": "24h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": true,
        "patch": true,
        "build": true,
        "digest": false,
        "scheme_change": false
    },
    "lagPolicy": {
        "major": 2,
        "minor": 1
    }
}
```

---

## Rule Properties

### `minImageAge`

Minimum age an image must have before it can be applied.

- **Type:** Duration
- **Required:** Yes
- **Purpose:** Prevents updating to brand-new images that might have issues

**Example:**
```json
"minImageAge": "3h"
```

### `progressiveUpgrade`

Whether to apply multiple version updates progressively.

- **Type:** Boolean
- **Required:** No
- **Default:** `false`

**Options:**
- `true`: Apply updates one at a time (1.0 → 1.1 → 1.2 → 2.0)
- `false`: Jump directly to latest allowed version (1.0 → 2.0)

**Example:**
```json
"progressiveUpgrade": true
```

### `allow`

Defines which update types are allowed.

- **Type:** Object
- **Required:** Yes

**Properties:**
- `major`: Major version updates (1.x.x → 2.x.x)
- `minor`: Minor version updates (1.1.x → 1.2.x)
- `patch`: Patch version updates (1.1.1 → 1.1.2)
- `build`: Build version updates (1.1.1-1 → 1.1.1-2)
- `digest`: Digest updates (same tag, different image)
- `scheme_change`: Versioning scheme changes (1.2.3 → 2024.01.15)

**Example:**
```json
"allow": {
    "major": false,
    "minor": true,
    "patch": true,
    "build": true,
    "digest": true,
    "scheme_change": false
}
```

### `conditions`

Conditional requirements for allowing specific update types.

- **Type:** Object
- **Required:** No

**Format:**
```json
"conditions": {
    "update_type": {
        "require": ["other_update_type1", "other_update_type2"]
    }
}
```

**Purpose:** Only allow an update type if other versions also exist.

**Example:**
```json
"conditions": {
    "major": {
        "require": ["minor", "patch", "build"]
    },
    "minor": {
        "require": ["patch"]
    }
}
```

**Meaning:**
- Major updates only if minor, patch, and build versions also exist
- Minor updates only if patch version also exists

### `lagPolicy`

Stay N versions behind the latest version.

- **Type:** Object
- **Required:** No

**Format:**
```json
"lagPolicy": {
    "major": 1,
    "minor": 2
}
```

**Meaning:**
- Stay 1 major version behind latest
- Stay 2 minor versions behind latest

**Example Scenario:**
- Latest version: 3.5.2
- Major lag: 1 → Allow up to 2.x.x
- Minor lag: 2 → Allow up to 2.3.x

**Example:**
```json
"lagPolicy": {
    "major": 1
}
```

---

## Complete Example

Here's a complete configuration example with all sections:

```ini
# captn Configuration
# ===================

[general]
dryRun = false
cronSchedule = 30 2 * * *

[logging]
level = INFO

[notifiers]
enabled = true

[notifiers.telegram]
enabled = true
token = 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
chatId = 123456789

[notifiers.email]
enabled = false
smtpServer = smtp.gmail.com
smtpPort = 587
username = your-email@gmail.com
password = your-app-password
fromAddr = captn@yourdomain.com
toAddr = admin@yourdomain.com

[update]
delayBetweenUpdates = 2m

[updateVerification]
maxWait = 480s
stableTime = 15s
checkInterval = 5s
gracePeriod = 15s

[prune]
removeUnusedImages = true
removeOldContainers = true
minBackupAge = 48h
minBackupsToKeep = 2

[selfUpdate]
removeHelperContainer = true

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

[docker]
apiUrl = https://registry.hub.docker.com/v2
pageCrawlLimit = 1000
pageSize = 100

[ghcr]
apiUrl = https://ghcr.io/v2
pageCrawlLimit = 1000
pageSize = 100

[registryAuth]
enabled = false
credentialsFile = /app/conf/registry-credentials.json

[envFiltering]
enabled = true
excludePatterns = [
    "BUILD_*",
    "GIT_*"
]
preservePatterns = [
    "TZ",
    "PUID",
    "PGID",
    "UMASK"
]
containerSpecificRules = {
    "immich": {
        "excludePatterns": [
            "IMMICH_BUILD_*"
        ],
        "preservePatterns": [
            "IMMICH_ENV"
        ]
    }
}

[assignmentsByName]
# Production databases
postgres-prod = conservative
mysql-prod = conservative
mariadb-prod = conservative

# Production web servers
nginx-prod = patch_only
apache-prod = patch_only

# Production caches
redis-prod = permissive
memcached-prod = permissive

# Development containers
dev-* = permissive

# Staging containers
staging-* = relaxed

[rules]
# Custom rule for critical services
critical_service = {
    "minImageAge": "48h",
    "progressiveUpgrade": true,
    "allow": {
        "major": false,
        "minor": false,
        "patch": true,
        "build": false,
        "digest": true,
        "scheme_change": false
    },
    "lagPolicy": {
        "major": 1
    }
}

# Custom rule for test services
test_service = {
    "minImageAge": "1h",
    "progressiveUpgrade": false,
    "allow": {
        "major": true,
        "minor": true,
        "patch": true,
        "build": true,
        "digest": true,
        "scheme_change": true
    }
}
```

---

**Next:** [Scripts Guide →](04-Scripts.md)

**Previous:** [← CLI Reference](02-CLI-Reference.md)

