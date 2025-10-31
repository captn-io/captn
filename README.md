<div align="center">
  <img src="https://raw.githubusercontent.com/captn-io/captn/main/app/assets/icons/app-icon.svg" alt="captn logo" width="120" height="120">
  <h1>captn</h1>
  <p><strong>Intelligent Container Updater</strong></p>
</div>

---

<p align="center">
  <strong>captn</strong> is an intelligent, rule-based container updater that automatically manages container updates using semantic versioning and registry metadata.<br>
  <em>Keep your containers up-to-date with confidence and control.</em>
</p>

<div align="center">

[![Docker Pulls](https://img.shields.io/docker/pulls/captnio/captn)](https://hub.docker.com/r/captnio/captn)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/captn-io/captn)](https://github.com/captn-io/captn/releases)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

</div>

## ✨ Features

- 🎯 **Rule-Driven Updates** - Define custom update policies for different containers
- 🌐 **Multi-Registry Support** - Docker Hub, GitHub Container Registry
- 📈 **Progressive Upgrades** - Apply multiple updates in sequence
- 👀 **Dry-Run Mode** - Preview changes before applying them
- 📰 **Notifications** - Get notified about update status and results via Telegram and E-Mail
- 🧹 **Automatic Cleanup** - Remove unused images and old backup containers
- 📊 **Comprehensive Logging** - Detailed logging with configurable levels
- ⏮️ **Rollback Support** - Automatic rollback on container startup and custom post-script failures
- ⏰ **Scheduled Execution** - Built-in scheduler with cron expression support

## 🚧 Development Status

> **Note**: This project is currently in an **early and active development phase**. While captn is functional and ready for testing, we're continuously improving and adding new features.

> **⚠️ Docker Compose**: captn has been developed and tested exclusively with containers created via `docker run` commands. **Docker Compose support is currently untested** and may not work as expected. If you're using Docker Compose and encounter issues, please report them so we may improve compatibility if possible.

**We welcome testers and contributors!** If you'd like to help shape captn, we're especially looking for contributions in:

- **📝 Documentation** - Help improve guides, examples, and explanations
- **🧪 Testing** - Test captn in different environments and report issues
- **🏗️ Repository Optimization** - Create wiki pages, issue templates, and improve project structure

Your feedback and contributions are highly valued as we work towards a stable release!

## 🚀 Quick Start

### 1. Create Directories

```bash
# Create directories for configuration and log files
mkdir -p ~/captn/{conf,logs}
```

### 2. Run captn Container

```bash
# Run captn container with proper volume mounts
docker run -d \
  --name captn \
  --restart unless-stopped \
  -e TZ=Europe/Berlin \
  -v /etc/localtime:/etc/localtime:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v ~/captn/conf:/app/conf \
  -v ~/captn/logs:/app/logs \
  captnio/captn:0.8.2
```

### 3. First Run (Dry-Run Mode)

By default, captn runs in normal mode but all containers are assigned to the `default` rule which **does not allow any updates at all** for safety reasons. To get a preview of what captn would do, you can:

  1. **Assign containers to different rules** in the configuration file
  2. **Run in dry-run mode** to see what would be updated:

      ```bash
      # Preview what would be updated
      docker exec captn captn --dry-run

      # Run actual updates (after reviewing dry-run results)
      docker exec captn captn
      ```

## 🔧 Advanced Features

### Pre/Post Scripts

captn supports executing custom scripts before and after updates:

- **Pre-scripts**: Run before container updates (backups, health checks)
- **Post-scripts**: Run after successful updates (verification, notifications, customizations, post-update or cleanup tasks)
- **Container-specific**: Scripts can be tailored to specific containers
- **Failure handling**: Configure whether to continue or skip/rollback on script failures

### Notifications

Get updates about captn's activities:

- Update status and results
- Error notifications
- Summary reports

#### Currently supported notification methods

- **Telegram**: Quick update summaries via Telegram Bot API
- **E-Mail**: SMTP-based email notifications with detailed HTML reports

## 📚 Documentation

For detailed configuration options, advanced usage, and troubleshooting, please refer to:

- **[Introduction & Getting Started](https://github.com/captn-io/captn/blob/main/docs/01-Introduction.md)** - Overview and concepts
- **[CLI Reference](https://github.com/captn-io/captn/blob/main/docs/02-CLI-Reference.md)** - Command-line usage
- **[Configuration Reference](https://github.com/captn-io/captn/blob/main/docs/03-Configuration.md)** - All configuration options
- **[Scripts Guide](https://github.com/captn-io/captn/blob/main/docs/04-Scripts.md)** - Pre/post-update scripts

## 🤝 Contributing

We welcome contributions! captn is in active development and we're particularly interested in:

- **Documentation improvements** - Enhance existing docs, add examples, create tutorials
- **Testing and bug reports** - Help us identify and fix issues
- **Repository infrastructure** - Help create wiki pages, issue templates, PR templates, and improve project organization
- **Code contributions** - New features, optimizations, and bug fixes

Feel free to open an issue to discuss your ideas or submit a pull request directly. Every contribution, no matter how small, is appreciated!

## 📄 License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)** - see the [LICENSE](https://github.com/captn-io/captn/blob/main/LICENSE) file for details.

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/captn-io/captn/issues)
- **Discussions**: [GitHub Discussions](https://github.com/captn-io/captn/discussions)
- **Documentation**: [Docs](https://github.com/captn-io/captn/blob/main/docs/01-Introduction.md)

---

**⚠️ Important**: Always test with `--dry-run` first to understand what captn will do before running actual updates.


<div align="center">
  <p>Brewed with ❤️ and loads of 🍺</p>
  <p>
    <a href="https://github.com/captn-io/captn">GitHub</a> •
    <a href="https://hub.docker.com/r/captnio/captn">Docker Hub</a> •
    <a href="https://github.com/captn-io/captn/issues">Issues</a>
  </p>
</div>
