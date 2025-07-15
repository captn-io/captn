# TODO - captn Project Roadmap

This document outlines the planned features and improvements for the captn container updater project.

## High Priority Features

### Project Foundation
- [x] **Project Rebranding** - Rebrand
- [x] **GitHub Space Name** - Chose "captn-io" / "captn.io" for GitHub organization
- [x] **Docker Hub Account** - Created personal account "captnio" for free hosting

#### Project Naming Analysis

##### Top Candidates (0 Collisions)
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

##### Personal Top 3 Recommendations
1. **captn** - Short, memorable, and fits the nautical/container theme
2. **KontainIQ** - Perfect balance of creativity and clarity
3. **Vermate** - Friendly and `verm8` is a cool CLI name
4. **Tideclock** - Poetic and functional at the same time

##### Rebranding Decision
After careful consideration, **captn** was chosen as the final name because:
- It's short, memorable, and easy to type
- The nautical theme fits well with container management
- It's unique and has no naming conflicts
- The CLI command `captn` is intuitive and professional

##### Project Accounts
- **GitHub**: [@captn-io/captn](https://github.com/captn-io/captn)
- **Docker Hub**: [@captnio](https://app.docker.com/accounts/captnio)


### Core Functionality
- [ ] **Remove cron dependency** - Integrate built-in scheduling service with cron expression support in config
- [ ] **Webhook integration** - Evaluate using webhooks to speed up update process
- [ ] **Pre/post-update scripts** - Integrate optional pre- and post-update script execution
- [ ] **Self-update functionality** - Implement ability for captn to update itself
- [ ] **Container network config verification** - Verify takeover of container's network configs and tmpfs
- [ ] **Docker Compose Support** - Evaluate and implement how captn should handle Docker Compose deployments (possibly define an update type in the configuration)
- [x] **CLI Auto-Completion** - Provide intelligent tab-completion for commands and options

### Monitoring & Logging
- [x] **Log file management** - Add CLI parameter to delete all log files before starting
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
- [x] **Drop Docker env vars** - Remove support for Docker environment variables due to complexity
- [ ] **Container config manipulation** - Allow slight manipulation of container config in configuration
  - [ ] Let users decide which configs should not be re-used from original container
- [x] **Configuration validation** - Add validation for configuration settings right in the beginning
  - [x] Verify the general structure of the configuration file
  - [x] Verify values (if applicable)
- [ ] **Default settings documentation** - Provide comprehensive documentation for default configuration

## Documentation

- [ ] **Complete rewrite** - Write entirely new documentation
- [ ] **API reference** - Comprehensive API documentation
- [ ] **Examples** - Real-world usage examples
- [ ] **Troubleshooting guide** - Common issues and solutions

## CI/CD Pipeline

### Quality Assurance
- [ ] **Code quality testing** - Implement automated code quality checks
- [x] **Multi-arch Docker images** - Create and publish multi-architecture Docker images on Docker Hub
- [ ] **Binary distribution** - Consider creation of standalone binary files (future consideration)

### Release Management
- [x] **Automated releases** - Set up automated release process
- [x] **Version tagging** - Implement semantic versioning
- [ ] **Changelog generation** - Automated changelog creation

## Legal & Licensing

### License Selection
- [ ] **Choose open source license** - Select appropriate license for open source protection
  - [ ] **MIT License** - Simple, permissive, widely used, good for commercial use
  - [ ] **Apache 2.0** - Patent protection, corporate-friendly, requires attribution
  - [ ] **GPL v3** - Copyleft, ensures derivatives stay open source
  - [ ] **AGPL v3** - Network copyleft, covers SaaS usage
  - [ ] **MPL 2.0** - File-level copyleft, good middle ground
- [ ] **Add license file** - Create LICENSE file with chosen license
- [ ] **Update README** - Add license badge and section
- [ ] **Copyright headers** - Add copyright headers to source files
- [ ] **License compliance check** - Verify all dependencies are compatible

### Code Protection
- [ ] **Source code protection** - Ensure code remains open while protecting against abuse
  - [ ] **Terms of service** - Define acceptable use policy
  - [ ] **Attribution requirements** - Ensure proper credit for contributions

## Monetization & Support

### Donation Platform Integration
- [ ] **Choose donation platform** - Select appropriate platform for user support
  - [ ] **GitHub Sponsors** - Native GitHub integration, no fees for open source
  - [ ] **Buy Me a Coffee** - Simple, user-friendly, low fees
  - [ ] **Ko-fi** - One-time donations, good for creators
  - [ ] **Open Collective** - Transparent funding, good for communities
  - [ ] **Liberapay** - Recurring donations, open source focused
- [ ] **Add donation badges** - Include donation links in README and docs

### Implementation Tasks
- [ ] **README integration** - Add donation section to main README
- [ ] **Documentation** - Create SUPPORT.md with donation information
- [ ] **Social proof** - Display supporter count/badges
- [ ] **Tax compliance** - Ensure proper tax handling for donations

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