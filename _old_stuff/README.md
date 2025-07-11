# Docker Container Updater

For all the lazier and automation-loving nerds, constantly updating Docker containers can be a tedious chore. Enter the Docker Container Updater to save the day. It handles updates without relying on the "latest" tag or sticking to the current image tag, which might cause you to miss important updates. Instead, it plays by your rules!

<br>
<br>

---

🌱 This project is currently in its early stages, and any feedback on potential issues would be greatly appreciated.

---

<br>
<br>

## Features

- **🔄 Automated Container Updates**: Effortlessly update all your Docker containers on your host under your own conditions.
- **🧠 Smart Update Detection**: This tool creates a regex filter based on the currently used image tag and scans Docker Hub for any available updates. It automatically analyzes the version numbers specified in the image tags and identifies major, minor, patch, and build updates. It also handles simple digest updates automatically.
- **⚙️ Customizable and Conditional Update Rules**: Define highly precise update rules for each individual container.
- **🔁 Standard Update Sequence**: Updates follow the standard sequence: first digest, build, patch, minor, and then major updates. No updates are skipped.
- **🛠️ Backup and Rollback**: Backups of your containers are created before updates. If an update fails, the change is rolled back and the old container is restarted.
- **📧 Notifications**: Stay informed with detailed email and telegram reports
- **📜 Pre- and Post-Scripts Integration**: Integrate your own pre- and post-scripts to perform actions such as backing up configuration files or databases before any update and making adjustments to the container configuration after any update.

## Getting Started

> ⚠️ The default configuration has **test mode enabled**. Safety first 😉! After you've run your first test, checked for errors, and reviewed the generated Docker run commands, you can disable test mode in your configuration *(see [Configuration](#configuration))*.

### Choose your method
Here are two methods to get this tool up and running:

* [Method 1: Using the Docker image](#method-1-using-the-docker-image) (recommended)
* [Method 2: Directly on your Docker host as a normal Bash script executed by root](#method-2-run-this-script-directly-on-your-host)

### Method 1: Using the [Docker image](https://hub.docker.com/r/janjk/docker-container-updater)

> This method allows you to run a simple and dedicated Docker container that already includes all the necessary tools required by `dcu.sh`.

#### Using Docker CLI

##### Example Command

Use the following command to run `Docker Container Updater` with basic configuration and test mode explicitly enabled:

```bash
docker run  -d \
            --name=Docker-Container-Updater \
            --hostname=Docker-Container-Updater \
            --restart=always \
            --privileged \
            --tty \
            --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock \
            --mount type=bind,source=/etc/localtime,target=/etc/localtime,readonly \
            --env DCU_TEST_MODE=true \
            --env DCU_CRONTAB_EXECUTION_EXPRESSION='30 2 * * *' \
            janjk/docker-container-updater:latest
```

> ##### ℹ️ Explanation
> The bind mount of `/var/run/docker.sock` is necessary to provide full access to the Docker environment on the host. This socket file enables the container to communicate with your Docker daemon, allowing it to manage Docker containers, images, and other resources. Without this bind mount, `Docker Container Updater` would be isolated from the host's Docker environment and unable to perform tasks like creating, starting, stopping, removing containers, pulling new images etc.
> <br>
> <br>
> The `--privileged` flag is needed to grant the Docker container elevated permissions on the host system. This flag provides the container with extended capabilities, allowing it to perform tasks that require higher levels of access to the host’s resources and hardware. Specifically, it:
>
> 1. **Gives the container access to all resources** on the host, similar to the root user.
> 2. **Allows the container to modify kernel parameters** using sysctl or sysfs.
> 3. **Grants the container additional capabilities** that are typically restricted for security reasons.
>
> Using the `--privileged` flag is essential for certain operations that involve deep integration with the host system, such as managing network configurations, mounting filesystems, or interacting with hardware devices directly.
>
>`Docker Container Updater` relies on these extended permissions to perform its intended tasks effectively.

##### Data Persistence

To ensure data persistence, you should configure the following mounts:

```
--mount type=bind,source=<YOUR_LOCAL_PRE_SCRIPTS_PATH>,target=/usr/local/etc/container_update/pre-scripts \
--mount type=bind,source=<YOUR_LOCAL_POST_SCRIPTS_PATH>,target=/usr/local/etc/container_update/post-scripts \
--mount type=bind,source=<YOUR_LOCAL_LOGS_PATH>,target=/var/log \
```

##### Run Your First Test

After successfully starting `Docker Container Updater`, a cron job inside the container will automatically manage the update mechanism for your Docker containers based on the cron expression defined in `DCU_CRONTAB_EXECUTION_EXPRESSION`.

To manually execute the update process, run:

```
docker exec -it Docker-Container-Updater dcu --run
```

If you have already disabled test mode in your configuration, you can enforce using test mode for this one time execution by running the following command *(>= v2024.06.07-1)*:

```
docker exec -it Docker-Container-Updater dcu --dry-run
```

### Method 2: Run this script directly on your host

1. On your Docker host, navigate to the directory where the script `dcu.sh` should be downloaded
2. Download `dcu.sh` and make it executable _(this can be done manually or by using the following command):_
   ```bash
   wget --header='Accept: application/vnd.github.v3.raw' -O dcu.sh https://api.github.com/repos/jansppenrade2/Docker-Container-Updater/contents/dcu.sh?ref=main && chmod +x ./dcu.sh
   ```
3. Execute `./dcu.sh` with root privileges *(the first run will be in **test mode** and will also create the default configuration file)*
4. Customize the default configuration file according to your specific requirements *(see [Configuration](#configuration))*
5. Create a cron job for this script *(after testing 🫠)*

## Configuration

The Docker Container Updater utilizes a configuration file, by default located in `/usr/local/etc/container_update/container_update.ini`. This file contains all the settings and parameters necessary for `dcu.sh` to run. You have the flexibility to tailor the configuration file to your specific needs when executing `dcu.sh` directly on your Docker host. Alternatively, when opting to utilize the [Docker image](https://hub.docker.com/r/janjk/docker-container-updater), you can simply add the corresponding environment variables to your `docker run` command.

| Config File Parameter                                                   | Docker Environment Variable                                       | Description                                                                                                                                           | Default Value                                                   | Possible Values                                           |
|-------------------------------------------------------------------------|-------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|-----------------------------------------------------------|
| [general]  test_mode                                                    | DCU_TEST_MODE                                                     | Enables or disables test mode                                                                                                                         | `true`                                                          | `true`, `false`                                           |
| [general]  prune_images                                                 | DCU_PRUNE_IMAGES                                                  | Automatically prune unused images                                                                                                                     | `true`                                                          | `true`, `false`                                           |
| [general]  prune_container_backups                                      | DCU_PRUNE_CONTAINER_BACKUPS                                       | Automatically prune old container backups                                                                                                             | `true`                                                          | `true`, `false`                                           |
| [general]  container_backups_retention                                  | DCU_CONTAINER_BACKUPS_RETENTION                                   | Number of days to retain container backups                                                                                                            | `7`                                                             | Any positive integer                                      |
| [general]  container_backups_keep_last                                  | DCU_CONTAINER_BACKUPS_KEEP_LAST                                   | Number of last container backups to keep regardless of retention time                                                                                 | `1`                                                             | Any positive integer                                      |
| [general]  container_update_validation_time                             | DCU_CONTAINER_UPDATE_VALIDATION_TIME                              | Time in seconds to validate if a container runs successfully after an update                                                                          | `120`                                                           | Any positive integer                                      |
| [general]  update_rules                                                 | DCU_UPDATE_RULES                                                  | Rules for updating containers (see detailed explanation below)                                                                                        | `*[0.1.1-1,true]`                                               | Custom rules *(separated by space)*                       |
| [general]  docker_hub_api_url                                           | DCU_DOCKER_HUB_API_URL                                            | URL for the Docker Hub API                                                                                                                            | `https://registry.hub.docker.com/v2`                            | Any valid URL                                             |
| [general]  docker_hub_api_image_tags_page_size_limit                    | DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_SIZE_LIMIT                     | Number of tags to fetch per page from Docker Hub                                                                                                      | `100`                                                           | Positive integer (1-100)                                  |
| [general]  docker_hub_api_image_tags_page_crawl_limit                   | DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_CRAWL_LIMIT                    | Number of pages to crawl for tags from Docker Hub                                                                                                     | `10`                                                            | Any positive integer                                      |
| [general]  github_container_repository_api_url                          | DCU_GITHUB_CONTAINER_REPOSITORY_API_URL                           | URL for the GitHub Container Repository API                                                                                                           | `https://ghcr.io/v2`                                            | Any valid URL                                             |
| [general]  github_container_repository_api_image_tags_page_size_limit   | DCU_GITHUB_CONTAINER_REPOSITORY_API_IMAGE_TAGS_PAGE_SIZE_LIMIT    | Number of tags to fetch per page from GitHub Container Repository                                                                                     | `1000`                                                          | Positive integer (1-1000)                                 |
| [general]  github_container_repository_api_image_tags_page_crawl_limit  | DCU_GITHUB_CONTAINER_REPOSITORY_API_IMAGE_TAGS_PAGE_CRAWL_LIMIT   | Number of pages to crawl for tags from GitHub Container Repository                                                                                    | `10`                                                            | Any positive integer                                      |
| [general]  docker_hub_image_minimum_age                                 | DCU_DOCKER_HUB_IMAGE_MINIMUM_AGE                                  | Minimum age in seconds threshold for a newly pulled Docker image                                                                                      | `21600`                                                         | Any positive integer                                      |
| [general]  pre_scripts_folder                                           | DCU_PRE_SCRIPTS_FOLDER                                            | Folder containing pre-update scripts                                                                                                                  | `/usr/local/etc/container_update/pre-scripts`                   | Any valid directory path                                  |
| [general]  post_scripts_folder                                          | DCU_POST_SCRIPTS_FOLDER                                           | Folder containing post-update scripts                                                                                                                 | `/usr/local/etc/container_update/post-scripts`                  | Any valid directory path                                  |
| [paths]    tput                                                         |                                                                   | Path to the `tput` command                                                                                                                            | *(automatically detected by script)*                            | Any valid file path                                       |
| [paths]    gawk                                                         |                                                                   | Path to the `gawk` command                                                                                                                            | *(automatically detected by script)*                            | Any valid file path                                       |
| [paths]    cut                                                          |                                                                   | Path to the `cut` command                                                                                                                             | *(automatically detected by script)*                            | Any valid file path                                       |
| [paths]    docker                                                       |                                                                   | Path to the `docker` command                                                                                                                          | *(automatically detected by script)*                            | Any valid file path                                       |
| [paths]    grep                                                         |                                                                   | Path to the `grep` command                                                                                                                            | *(automatically detected by script)*                            | Any valid file path                                       |
| [paths]    jq                                                           |                                                                   | Path to the `jq` command                                                                                                                              | *(automatically detected by script)*                            | Any valid file path                                       |
| [paths]    sed                                                          |                                                                   | Path to the `sed` command                                                                                                                             | *(automatically detected by script)*                            | Any valid file path                                       |
| [paths]    wget                                                         |                                                                   | Path to the `wget` command                                                                                                                            | *(automatically detected by script)*                            | Any valid file path                                       |
| [paths]    sort                                                         |                                                                   | Path to the `sort` command                                                                                                                            | *(automatically detected by script)*                            | Any valid file path                                       |
| [paths]    sendmail                                                     |                                                                   | Path to the `sendmail` command                                                                                                                        | *(automatically detected by script)*                            | Any valid file path                                       |
| [log]      filePath                                                     | DCU_LOG_FILEPATH                                                  | Path to the log file                                                                                                                                  | `/var/log/container_update.log`                                 | Any valid file path                                       |
| [log]      level                                                        | DCU_LOG_LEVEL                                                     | Log level                                                                                                                                             | `INFO`                                                          | `DEBUG`, `INFO`, `WARN`, `ERROR`                          |
| [log]      retention                                                    | DCU_LOG_RETENTION                                                 | Number of days to retain log file entries                                                                                                             | `7`                                                             | Any positive integer                                      |
| [mail]     notifications_enabled                                        | DCU_MAIL_NOTIFICATIONS_ENABLED                                    | Enable or disable email notifications                                                                                                                 | `false`                                                         | `true`, `false`                                           |
| [mail]     mode                                                         | DCU_MAIL_NOTIFICATION_MODE                                        | Mode of sending emails  (currently only sendmail is supported)                                                                                        | `sendmail`                                                      | `sendmail`                                                |
| [mail]     from                                                         | DCU_MAIL_FROM                                                     | Email address for sending notifications                                                                                                               |                                                                 | Any valid email address                                   |
| [mail]     recipients                                                   | DCU_MAIL_RECIPIENTS                                               | Space-separated list of recipient email addresses                                                                                                     |                                                                 | Any valid email addresses *(separated by space)*          |
| [mail]     subject                                                      | DCU_MAIL_SUBJECT                                                  | Subject of the notification email                                                                                                                     | `Docker Container Update Report from <hostname>`                | Any valid string                                          |
|                                                                         | DCU_MAIL_RELAYHOST                                                | The relay host to which the Docker container's Postfix forwards its mails                                                                             |                                                                 | IP address or hostname and port (e.g.: `[10.1.1.30]:25` ) |
| [telegram] notifications_enabled                                        | DCU_TELEGRAM_NOTIFICATIONS_ENABLED                                | Enable or disable telegram notifications                                                                                                              | `false`                                                         | `true`, `false`                                           |
| [telegram] retry_limit                                                  | DCU_TELEGRAM_RETRY_LIMIT                                          | Number of retry attempts for sending a message                                                                                                        | 2                                                               | Any positive integer                                      |
| [telegram] retry_interval                                               | DCU_TELEGRAM_RETRY_INTERVAL                                       | Time interval between retry attempts (in seconds)                                                                                                     | 10                                                              | Any positive integer                                      |
| [telegram] chat_id                                                      | DCU_TELEGRAM_CHAT_ID                                              | Unique identifier for the target chat or user                                                                                                         |                                                                 | A single valid chat ID                                    |
| [telegram] bot_token                                                    | DCU_TELEGRAM_BOT_TOKEN                                            | Access token for the Telegram Bot API                                                                                                                 |                                                                 | A single valid Telegram Bot token                         |
|                                                                         | DCU_CRONTAB_EXECUTION_EXPRESSION                                  | Crontab expression for automating the update process execution. You can utilize [this site](https://crontab.cronhub.io/) to generate the expression   |                                                                 | Any valid crontab expression                              |
|                                                                         | DCU_CONFIG_FILE                                                   | Path to the INI configuration file inside the container. **Do not persist this!**                                                                     |                                                                 | Any valid file path                                       |
|                                                                         | DCU_REPORT_REAL_HOSTNAME                                          | Specify the hostname of your Docker host to override it in the reports. Otherwise, you will see the container's hostname instead                      |                                                                 | Any string                                                |
|                                                                         | DCU_REPORT_REAL_IP                                                | Specify the IP address of your Docker host to override it in the reports. Otherwise, you will see the container's IP address instead                  |                                                                 | Any string                                                |
|                                                                         | DCU_REPORT_REAL_DOCKER_VERSION                                    | Specify the Docker version used by your Docker host to override it in the reports. Otherwise, you will see the container's Docker version instead     |                                                                 | Any string                                                |

### Configure Notifications

#### E-Mail Notifications

##### General Information

If you are running the `dcu.sh` script directly on your Docker host, you just need to ensure that `sendmail` is installed and configured on your Docker host.
If you are using the [Docker image](https://hub.docker.com/r/janjk/docker-container-updater), you need to have a Mail Transfer Agent (MTA) (e.g., Postfix) installed, configured and reachable in your network, to which the Docker container can relay its emails. The IP address or the hostname of your MTA needs be specified in the environment variable `DCU_MAIL_RELAYHOST` when running the container.

##### Docker CLI
```
--env DCU_REPORT_REAL_HOSTNAME="$(hostname)" \
--env DCU_REPORT_REAL_IP="$(hostname -I | awk '{print $1}')" \
--env DCU_REPORT_REAL_DOCKER_VERSION="$(docker --version | awk '{print $3}' | tr -d ',')" \
--env DCU_MAIL_NOTIFICATIONS_ENABLED=true \
--env DCU_MAIL_FROM='<some@mail.address>' \
--env DCU_MAIL_RECIPIENTS='<some@mail.address>' \
--env DCU_MAIL_SUBJECT="🐳 Docker Container Update Report from $(hostname)" \
--env DCU_MAIL_RELAYHOST='[<IP address or hostname>]:<Port>' \
```

##### Configuration File
```
[mail]
notifications_enabled=true
mode=sendmail
from=<some@mail.address>
recipients=<some@mail.address>
subject=🐳 Docker Container Update Report from MyDockerHostName
```

#### Telegram Notificationss

##### General Information

To receive Telegram notifications, you first need to obtain a Chat ID and a Bot Token.

##### Docker CLI
```
--env DCU_REPORT_REAL_HOSTNAME="$(hostname)" \
--env DCU_REPORT_REAL_IP="$(hostname -I | awk '{print $1}')" \
--env DCU_REPORT_REAL_DOCKER_VERSION="$(docker --version | awk '{print $3}' | tr -d ',')" \
--env DCU_TELEGRAM_NOTIFICATIONS_ENABLED=true \
--env DCU_TELEGRAM_BOT_TOKEN='<your_bot_token>' \
--env DCU_TELEGRAM_CHAT_ID='<your_chat_id' \
```

##### Configuration File
```
[telegram]
notifications_enabled=true
retry_limit=2
retry_interval=10
chat_id=<your_bot_token>
bot_token=<your_chat_id
```

### Configure Update Rules

The `update_rules` parameter, or `DCU_UPDATE_RULES` environment variable allows you to define the update behavior for your containers. The default rule is `*[0.1.1-1,true]`, which means:

- `*`: Applies to all containers.
- `0.1.1-1`: Specifies the update policy, where each number represents:
  - `0`: Major updates *(0 means no major updates, 1 means allow major updates to the next available, 2 means always stay one version behind the latest major release, and so on)*
  - `1`: Minor updates *(0 means no minor updates, 1 means allow minor updates to the next available, 2 means always stay one version behind the latest minor release, and so on)*
  - `1`: Patch updates *(0 means no patch updates, 1 means allow patch updates to the next available, 2 means always stay one version behind the latest patch release, and so on)*
  - `1`: Build updates *(0 means no build updates, 1 means allow build updates to the next available, 2 means always stay one version behind the latest build release, and so on)*
- `true`: Indicates that digest updates are allowed.

You can customize these rules for each container by specifying different patterns and update policies separated by spaces.

#### Basic Rule Example

```
*[0.1.1-1,true] mycontainer[1.0.0-1,true] another[0.0.1-1,false] further[2.1.1-1,true]
```

> This example configuration means:
>
> - All containers are allowed to apply only minor, patch, build, and digest updates.
> - The container named `mycontainer` is allowed to apply major, build, and digest updates.
> - The container named `another` is allowed to apply only patch and build updates.
> - The container named `further` is allowed to apply major updates only when the latest release is two versions higher *(e.g., if Nextcloud releases version 29.0.0 and your Nextcloud is on version 27.0.0, an update to version 28.0.0 will be performed)*.

#### Precise Rule Examples

You can also create more specific rule sets that allow, for example, major updates for a container if at least one patch has been released for that major version.
In the rules, 'M' stands for Major, 'm' for Minor, 'p' for Patch, and 'b' for Build.

```
mycontainer[1&(p>1).1.1-1,true]
```

> This rule allows major updates for the container `mycontainer` if at least one patch version greater than 1 has been released for this major version.

```
mycontainer[0.1&(b>2).1-1,true]
```

> This rule allows minor updates for the container `mycontainer` if the build version is greater than 2.

These precise rules provide granular control over the update behavior of specific containers based on various conditions such as patch versions, build versions, and more.

> ℹ️ These rules do not affect the order in which updates are installed! An update is never skipped.

---

### Pre- and Post-Scripts

To give you more control, you can integrate your own pre- and post-scripts. These are created by default in the directories `/usr/local/etc/container_update/pre-scripts` and `/usr/local/etc/container_update/post-scripts` *(if you are using the Docker container, you can find these directories within the container, or at the mounted location)*, and they must be named after the relevant container. These are standard bash scripts that you can create and customize as needed. For example, you can create backups of databases, configuration files, etc., before updating a container, and make adjustments such as customized branding or changes to file permissions after any update. Essentially, you can tailor these scripts to your specific needs. The output of these scripts is redirected to the log of `Docker Container Updater`, so you have all logs in one place.

#### When are the Pre- and Post-Scripts executed?

##### Description of the Update Process

1. A **pre-script** is executed as soon as all conditions for an update are met:
   - The effective rule for the respective container allows an update
   - The age of the image on Docker Hub meets the configured minimum age in `DCU_DOCKER_HUB_IMAGE_MINIMUM_AGE` or in `docker_hub_image_minimum_age`
   - The new image has been successfully downloaded

   > Only at this point is the pre-script executed. Once the pre-script has been processed, the procedure continues as follows...

2. The original container is renamed *(to allow for a backup of the container)*
3. The startup policy of the original container is overwritten *(to prevent simultaneous startups)*
4. The original container is stopped
5. The new container with the new image is started
7. If the new container was successfully started, the **post-script** is now executed.

> ℹ️ A little tip if you are using `Docker Container Updater` as a container:
>
> To gain full access to the directories of individual Docker containers, you may need to mount additional directories into `Docker Container Updater`. There are various approaches to this, which vary depending on the system your architecture/design. Decide for yourself what works best for you.

## Command Line Parameters

```
Usage: dcu [ [--dry-run|--run] [--filter name|id=VALUE] [--force] ] [--help] [--version]
Options:
  --dry-run    -dr        Run DCU in dry-run mode (this temporarily enforces test mode to be enabled)
  --force      -f         Force lock acquisition
  --help       -?         Display this help
  --run        -r         Run DCU (considering the current configuration for test mode)
  --version    -v         Display the current version
  --debug                 Set log level to debug mode

Usage: dcu [--dry-run|--run] [ --filter [options|--help] ]
Options:
  --filter                Filter processed containers by the following conditions:
                            name=My_Container_Name
                            id=My_Container_ID
```

---

## Having Trouble?
If you encounter any issues while executing this script, please provide the following information:
- A full log in debug mode *(ensure sensitive data is replaced)*
- A `docker container inspect` of one or more affected containers *(ensure sensitive data is replaced)*
- A `docker image inspect` of one or more images *(ensure sensitive data is replaced)*

---
