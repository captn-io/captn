# TODO - captn Project Roadmap

This document outlines the planned features and improvements for the captn container updater project.

## High Priority Features

### Core Functionality
- [ ] **Remove cron dependency** - Integrate built-in scheduling service with cron expression support in config
- [ ] **Webhook integration** - Evaluate using webhooks to speed up update process
- [ ] **Pre/post-update scripts** - Integrate optional pre- and post-update script execution
- [ ] **Self-update functionality** - Implement ability for captn to update itself
- [ ] **Container network config verification** - Verify takeover of container's network configs and tmpfs
- [x] **CLI Auto-Completion** - Provide intelligent tab-completion for commands and options

### Monitoring & Logging
- [ ] **Enhanced logging** - Log docker inspect output before and after updates
- [ ] **Change threshold warnings** - Trigger warnings when configurable threshold of differences is exceeded
- [ ] **Code cleanup** - Search for and rename all `_*` functions

## Backup and Restore System

### Configuration Structure
```ini
[BackupRestore]
ContainerName = {
  backupImage = true
  dbType = postgresql
  dbUser = root
  dbPassword = myPass
  dbName = databasename
  filesAndFolders = [
    /full/path/to/appdata/and/volumes/myConfig/folder,
    /another/one/,
    /this/is/a/file.txt
  ]
}
```

### CLI Commands
- [ ] **Backup CLI** - `captn backup <ContainerName> [--db|--appdata|--image|--all]`
- [ ] **Restore CLI** - `captn restore <ContainerName> [--db|--appdata|--image|--all]`
- [ ] **Backup storage** - Create backups in mounted directory of container

## Notification System

### Notification Format
- [ ] **Define clear format** - Establish essential information structure and readability
- [ ] **Log file attachments** - Support optional log file attachments for email notifications
  - [ ] On failure only
  - [ ] Always
  - [ ] Never

### Notification Channels
- [ ] **Telegram notifications** - Implement Telegram-based notifications
- [ ] **SMTP email notifications** - Implement SMTP-based email notifications

## Configuration Improvements

### Configuration Management
- [ ] **Drop Docker env vars** - Remove support for Docker environment variables due to complexity
- [ ] **Container config manipulation** - Allow slight manipulation of container config in configuration
  - [ ] Let users decide which configs should not be re-used from original container
- [ ] **Configuration validation** - Add validation for configuration settings
- [ ] **Default settings documentation** - Provide comprehensive documentation for default configuration

## Documentation

- [ ] **Complete rewrite** - Write entirely new documentation
- [ ] **API reference** - Comprehensive API documentation
- [ ] **Examples** - Real-world usage examples
- [ ] **Troubleshooting guide** - Common issues and solutions

## CI/CD Pipeline

### Quality Assurance
- [ ] **Code quality testing** - Implement automated code quality checks
- [ ] **Multi-arch Docker images** - Create and publish multi-architecture Docker images on Docker Hub
- [ ] **Binary distribution** - Consider creation of standalone binary files (future consideration)

### Release Management
- [ ] **Automated releases** - Set up automated release process
- [ ] **Version tagging** - Implement semantic versioning
- [ ] **Changelog generation** - Automated changelog creation

## Project Naming Analysis

The project is currently named **captn** (Captain without vowels). Here's the analysis of alternative names:

### Top Candidates (0 Collisions)
| Name           | CLI Name     | Notes                                       |
| -------------- | ------------ | ------------------------------------------- |
| **KontainIQ**  | `kontainiq`  | Creative, technical, memorable              |
| **Regin**      | `regin`      | Short, nerdy, Rule Engine reference         |
| **Shipctl**    | `shipctl`    | CLI-like, nautical, professional            |
| **Updrafter**  | `updrafter`  | Metaphorically strong, updates "rise"       |
| **Verbot**     | `verbot`     | Clever (Version Bot), German double meaning |
| **Vermate**    | `verm8`      | Friendly, technical, cool CLI name          |
| **Boatswain**  | `boatswain`  | Traditional nautical, unusual               |
| **Deckhand**   | `deckhand`   | Modest, works in background                 |
| **Harbourctl** | `harbourctl` | Professional, CLI-like                      |
| **Mooring**    | `mooring`    | Poetic, containers "dock"                   |
| **Tideclock**  | `tideclock`  | Regular cycles, very fitting                |

### Personal Top 3 Recommendations
1. **KontainIQ** - Perfect balance of creativity and clarity
2. **Vermate** - Friendly and `verm8` is a cool CLI name
3. **Tideclock** - Poetic and functional at the same time

## Issue Templates

### Feature Request Template
```markdown
## Feature Request

### Description
Brief description of the feature

### Use Case
Why is this feature needed?

### Proposed Solution
How should this feature work?

### Alternatives Considered
What other approaches were considered?

### Additional Context
Any other relevant information
```

### Bug Report Template
```markdown
## Bug Report

### Description
Clear description of the bug

### Steps to Reproduce
1. Step 1
2. Step 2
3. Step 3

### Expected Behavior
What should happen

### Actual Behavior
What actually happens

### Environment
- OS: [e.g. Ubuntu 20.04]
- captn version: [e.g. 1.0.0]
- Docker version: [e.g. 20.10.0]

### Additional Context
Logs, screenshots, etc.
```