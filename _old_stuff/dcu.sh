#!/bin/bash
#
# DOCKER CONTAINER UPDATER
# Automatic Docker Container Updater Script
#
# ## Version
# 2025.03.06-1
#
# ## Changelog
# 2025.03.06-1, janseppenrade2: Issue: Increased default limits for ghcr.io
# 2024.12.08-1, janseppenrade2: Issue #36: Self-Update still broken in some cases
# 2024.12.06-1, janseppenrade2: Issue #35: Self-Update broken again
# 2024.12.04-2, janseppenrade2: Issue #32: Leading zeros in version parts cause errors
# 2024.11.08-2, janseppenrade2: Hotfix: Self Update not possible
# 2024.11.08-1, janseppenrade2: Issue #28: Added support for GitHub Container Registry (ghcr.io). IMPORTANT: Digest updates and MINIMUM AGE filtering for images on ghcr.io are currently not supported — additional development is needed. Optimized log layout. Fixed an issue when executing "dcu --version" before a config was created.
# 2024.10.04-1, janseppenrade2: Issue #27: Removed reliance on tput and added an alternative using stty. Also updated the logs with improved line symbols (”|” -> “║”, “=” -> “═”, “╔”)
# 2024.07.25-1, janseppenrade2: Issue: Fixed an issue where the Get-ContainerPropertyUnique function accidentally removed quotation marks in environment variables - This resulted in error bringing up the new container.
# 2024.06.21-1, janseppenrade2: Issue: Fixed an issue occurring when the retrieved list of image tags was too large.
# 2024.06.17-1, janseppenrade2: Issue: Caught an error that caused the script to enter an infinite loop if the executing user lacked the necessary permissions to create the log file. Added some more command line parameters. Optimized self-update.
# 2024.06.10-1, janseppenrade2: Issue: Fixed a bug that occurred when a mount contained a backslash
# 2024.06.07-1, janseppenrade2: Added command line arguments
# 2024.06.06-1, janseppenrade2: Issue: Fixed a bug that caused the accidentally interpretation of asterisks in container and image configurations.
# 2024.06.05-1, janseppenrade2: Issue: Fixed a bug that prevented the addition of non-persistent mounts in the docker run command (introduced in the previous bugfix, version 2024.06.03-1). Added support for self-update. Renamed the script file from container_update.sh to dcu.sh to prepare for simpler and more consistent directories and commands.
# 2024.06.03-1, janseppenrade2: Issue #16: Bind Mounts not taken over to new container after update
# 2024.05.31-1, janseppenrade2: Issue #14: Issue: Blocking rule not shown in update report (Mail only)
# 2024.05.31-1, janseppenrade2: Issue #13: Version Recognition in some cases not working
# 2024.05.30-1, janseppenrade2: Issue #11: Digests not compared correctly
# 2024.05.29-1, janseppenrade2: Implemented functionality to retrieve and display the Docker host's information (hostname, IP address, and Docker version) in the reports when running the Docker Container Updater as a Docker container by passing this information via the environment variables `DCU_REPORT_REAL_HOSTNAME`, `DCU_REPORT_REAL_IP` and `DCU_REPORT_REAL_DOCKER_VERSION`.
# 2024.05.28-2, janseppenrade2: Added support for container attribute "--tty". Prevented self update in case Docker Container Updater is running in a Docker Container.
# 2024.05.27-3, janseppenrade2: Fixed a bug that caused notifications to be sent even when no action was taken. Additionally, fixed an issue with log file pruning that resulted in the removal of various spaces, which were important for maintaining readability in the log file.
# 2024.05.27-2, janseppenrade2: Fixed a bug that reported incorrectly listed outstanding updates if an update was already performed during the same script execution.
# 2024.05.27-1, Keonik1: Add docker container installation, refactor some functions.
# 2024.05.26-1, janseppenrade2: Addressed a minor bug that prevented removed container backups from being listed in reports. Addressed a bug that caused an unexpected script termination on QNAP devices with an outdated version of 'date'. Added support for Telegram notifications. Some optimizations to Extract-VersionPart() (responsible for detecting Major, Minor, Patch, and Build updates). Fixed a malformed table in generated HTML mail reports. Optimized outstanding updates list in report. Fixed a bug in the update rule analysis related to build updates.
# 2024.05.21-3, janseppenrade2: Addressed a minor bug that was impacting the sorting of available image tags
# 2024.05.21-2, janseppenrade2: Added support for container attribute "--privileged"
# 2024.05.21-1, janseppenrade2: Fixed a typo in the email report and resolved an issue that sometimes caused the Docker version to be omitted from the email report. Additionally, support for defining a minimum age (docker_hub_image_minimum_age) for new Docker Hub image tags has been added.
# 2024.05.17-1, janseppenrade2: Fixed a minor bug that prevented an email report from being generated when updates were found but no changes were made. (Those reports might be important for those who using this script just to monitor updates)
# 2024.05.16-1, janseppenrade2: Completely redesigned for enhanced performance and a better overview and more reliability - Crafted with lots of love and a touch of magic

configFile=${DCU_CONFIG_FILE:-"/usr/local/etc/container_update/container_update.ini"}
pidFile="$(dirname "$(readlink -f "$0")")/`basename "$0"`.pid"
test_mode=""
logLevel=""
start_time=$(date +%s)
stats_execution_time=0
stats_errors_count=0
stats_warnings_count=0
report_available=false
mail_report_actions_taken=""
mail_report_available_updates=""
mail_report_removed_container_backups=""
telegram_report_actions_taken=""
telegram_report_available_updates=""
telegram_report_removed_container_backups=""
self_update_helper_container_name=""
self_update_helper_container_started=false

Acquire-Lock() {
    local pidFile_creation_time=""
    local pidFile_age=""
    local current_time=""
    local script_timeout=10800 # 3 hours
    local test_mode=$test_mode

    [ "$test_mode" == false ] && sleep $((RANDOM % 5))
    if test -f "$pidFile"; then
        pidFile_creation_time=$(stat -c %Y "$pidFile")
        current_time=$(date +%s)
        pidFile_age=$((current_time - pidFile_creation_time))
        if (( pidFile_age > $script_timeout )); then
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] INFO        The PID file is older than $script_timeout seconds. Forcing lock acquisition..."
            rm -f "$pidFile" || { Write-Log "ERROR" "Failed to remove \"$pidFile\""; End-Script 1; }
        else
            remaining=$((script_timeout - pidFile_age))
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] WARNING     The PID file was created less than $script_timeout seconds ago"
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] INFO        Able to force acquisition in $remaining seconds"
            exit 0
        fi
    fi
    echo $$ > "$pidFile" || { echo "[$(date +%Y/%m/%d\ %H:%M:%S)] ERROR       Failed to create \"$pidFile\""; exit 1; }
    start_time=$(date +%s)
}

End-Script() {
    local exitcode=${1:-0}

    if [ -z "$exitcode" ]; then
        exitcode=0
    fi
    Write-Log "INFO"  "<print_line_top>"
    Write-Log "INFO"  "║  TEARDOWN"
    Write-Log "INFO"  "<print_line_btn>"

    Prune-Log $(Read-INI "$configFile" "log" "retention")

    Write-Log "INFO" "    Removing PID file (\"$pidFile\")"
    rm -f "$pidFile" 2>/dev/null || Write-Log "ERROR" "      => Failed to remove PID file (\"$pidFile\")"

    local end_time=$(date +%s)
    stats_execution_time=$((end_time - start_time))

    if [ $exitcode -gt 0 ]; then
        Write-Log "ERROR" "    Exiting with code $exitcode after an execution time of $stats_execution_time second(s) with $stats_warnings_count warning(s) and $stats_errors_count error(s)"
    else
        Write-Log "INFO" "    Script execution has been ended properly after $stats_execution_time second(s) with $stats_warnings_count warning(s) and $stats_errors_count error(s)"
    fi

    exit $exitcode
}

Read-INI() {
    local filePath="$1"
    local section="$2"
    local key="$3"
    local in_section=false

    if ! grep -q "^\[$section\]" "$filePath" 2>/dev/null; then
        return 1
    fi

    while IFS= read -r line; do
        if [[ "$line" == "[${section}]" ]]; then
            in_section=true
        elif [[ "$line" == "["* ]]; then
            in_section=false
        fi

        if $in_section; then
            if [[ "$line" == "${key} ="* || "$line" == "${key}="* ]]; then
                echo "$(echo $line | sed 's/^[^=]*= *//')"
                break
            fi
        fi
    done < "$filePath"

    return 1
}

Write-INI() {
    local filePath="$1"
    local section="$2"
    local key="$3"
    local value="$4"
    local in_section=false
    local line_number=1
    local found_key_in_section=false

    if ! grep -q "^\[$section\]" "$filePath"; then
        if [ ! -s "$filePath" ]; then
            echo "[$section]" >> "$filePath"
        else
            echo "" >> "$filePath"
            echo "[$section]" >> "$filePath"
        fi
    fi

    while IFS= read -r line; do
        if [[ "$line" == "[${section}]" ]]; then
            in_section=true
        elif [[ "$line" == "["* ]]; then
            in_section=false
        fi

        if $in_section; then
            if [[ "$line" == "${key} ="* || "$line" == "${key}="* ]]; then
                found_key_in_section=true
                sed -i "${line_number}s#.*#$key=$value#" "$filePath"
                break
            fi
        fi
        ((line_number++))
    done < "$filePath"

    if [ "$found_key_in_section" = false ]; then
        line_number=1
        while IFS= read -r line; do
            if [[ "$line" == "[${section}]" ]]; then
                sed -i "${line_number}a\\$key=$value" "$filePath"
                break
            fi
            ((line_number++))
        done < "$filePath"
    fi
}

Write-Log() {
    local level="$1"
    local message="$2"
    local logLevel="$logLevel" && [ -z $logLevel ] && logLevel=$(Read-INI "$configFile" "log" "level" | tr '[:lower:]' '[:upper:]')
    local logFile=$(Read-INI "$configFile" "log" "filePath")
    local cmd_tput=$(Read-INI "$configFile" "paths" "tput") && [ -z $cmd_tput ]  && cmd_tput="tput"
    local cmd_stty=$(Read-INI "$configFile" "paths" "stty") && [ -z $cmd_stty ]  && cmd_tput="stty"
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed") && [ -z $cmd_sed ]  && cmd_sed="sed"
    local cmd_tee=$(Read-INI "$configFile" "paths" "tee") && [ -z $cmd_tee ]  && cmd_tee="tee"
    local logFileFolder=$(dirname "$logFile")

    if [ -z "$logLevel" ] && test -f "$configFile"; then
        if [ -n "$logFile" ] && test -f "$logFile"; then
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] WARNING No log level configured. Using default of \"DEBUG\"" | $cmd_tee -a "$logFile"
        else
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] WARNING No log level configured. Using default of \"DEBUG\""
        fi
        ((stats_warnings_count++))
        logLevel="DEBUG"
    fi

    if [ -n "$logFileFolder" ] && [ -n "$logFile" ]; then
        mkdir -p $logFileFolder 2>/dev/null || End-Script 1
        touch "$logFile" 2>/dev/null || { echo "[$(date +%Y/%m/%d\ %H:%M:%S)] ERROR   Unable to create log file (\"$logFile\")" >&2; exit 1; }
    fi

    if [ "$logLevel" != "DEBUG" ] && [ "$logLevel" != "INFO" ] && [ "$logLevel" != "WARNING" ] && [ "$logLevel" != "ERROR" ]; then
        logLevel="DEBUG"
    fi

    if [[ "$message" == *"<print_line_top>"* ]] && [ -n "$cmd_tput" ] && [[ $($cmd_tput cols 2>/dev/null) =~ ^[0-9]+$ ]]; then
        local leading_spaces=$(expr match "$message" ' *')
        local cols=$(( $($cmd_tput cols) - ( 35 + $leading_spaces ) ))
        local line_prefix=$(printf "%-${leading_spaces}s" "")
        local line=$(printf "%0.s═" $(seq 1 $cols))
        message="${line_prefix}╔${line}"
    elif [[ "$message" == *"<print_line_top>"* ]] && [ -n "$cmd_stty" ] && [[ $($cmd_stty size < /dev/tty | cut -d' ' -f2-) =~ ^[0-9]+$ ]]; then
        local leading_spaces=$(expr match "$message" ' *')
        local cols=$(( $($cmd_stty size < /dev/tty | cut -d' ' -f2-) - ( 35 + $leading_spaces ) ))
        local line_prefix=$(printf "%-${leading_spaces}s" "")
        local line=$(printf "%0.s═" $(seq 1 $cols))
        message="${line_prefix}╔${line}"
    elif [[ "$message" == *"<print_line_top>"* ]]; then
        local line="╔═════════════════════════════════════════════════════════════"
        message=$(echo "$message" | "$cmd_sed" "s/<print_line_top>/$line/g")
    fi

    if [[ "$message" == *"<print_line_btn>"* ]] && [ -n "$cmd_tput" ] && [[ $($cmd_tput cols 2>/dev/null) =~ ^[0-9]+$ ]]; then
        local leading_spaces=$(expr match "$message" ' *')
        local cols=$(( $($cmd_tput cols) - ( 35 + $leading_spaces ) ))
        local line_prefix=$(printf "%-${leading_spaces}s" "")
        local line=$(printf "%0.s═" $(seq 1 $cols))
        message="${line_prefix}╚${line}"
    elif [[ "$message" == *"<print_line_btn>"* ]] && [ -n "$cmd_stty" ] && [[ $($cmd_stty size < /dev/tty | cut -d' ' -f2-) =~ ^[0-9]+$ ]]; then
        local leading_spaces=$(expr match "$message" ' *')
        local cols=$(( $($cmd_stty size < /dev/tty | cut -d' ' -f2-) - ( 35 + $leading_spaces ) ))
        local line_prefix=$(printf "%-${leading_spaces}s" "")
        local line=$(printf "%0.s═" $(seq 1 $cols))
        message="${line_prefix}╚${line}"
    elif [[ "$message" == *"<print_line_btn>"* ]]; then
        local line="╚═════════════════════════════════════════════════════════════"
        message=$(echo "$message" | "$cmd_sed" "s/<print_line_btn>/$line/g")
    fi

    if [ "$level" = "DEBUG" ] && { [ "$logLevel" = "DEBUG" ]; }; then
        if [ -n "$logFile" ] && test -f "$logFile"; then
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] $level   $message" | $cmd_tee -a "$logFile"
        else
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] $level   $message"
        fi
    elif [ "$level" = "INFO" ] && { [ "$logLevel" = "DEBUG" ] || [ "$logLevel" = "INFO" ]; }; then
        if [ -n "$logFile" ] && test -f "$logFile"; then
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] $level    $message" | $cmd_tee -a "$logFile"
        else
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] $level    $message"
        fi
    elif [ "$level" = "WARNING" ] && { [ "$logLevel" = "DEBUG" ] || [ "$logLevel" = "INFO" ] || [ "$logLevel" = "WARNING" ]; }; then
        if [ -n "$logFile" ] && test -f "$logFile"; then
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] $level $message" | $cmd_tee -a "$logFile"
        else
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] $level $message"
        fi
        ((stats_warnings_count++))
    elif [ "$level" = "ERROR" ] && { [ "$logLevel" = "DEBUG" ] || [ "$logLevel" = "INFO" ] || [ "$logLevel" = "WARNING" ] || [ "$logLevel" = "ERROR" ]; }; then
        if [ -n "$logFile" ] && test -f "$logFile"; then
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] $level   $message" | $cmd_tee -a "$logFile"
        else
            echo "[$(date +%Y/%m/%d\ %H:%M:%S)] $level   $message"
        fi
        ((stats_errors_count++))
    fi
}

Prune-Log() {
    local retention=${1:-7}
    local logFile=$(Read-INI "$configFile" "log" "filePath")
    local cmd_awk=$(Read-INI "$configFile" "paths" "gawk")

    if [ -n "$logFile" ] && test -f "$logFile"; then
        local current_time=$(date +%s)
        local timestamp=$(head -n 1 "$logFile" | $cmd_awk -F'[][]' '{print $2}')
        local timestamp_seconds=$(date -d "$timestamp" +%s)
        local difference=$(( (current_time - timestamp_seconds) / 86400 ))

        if [ "$difference" -gt "$retention" ]; then
            Write-Log "INFO" "    Pruning log file (Keeping entries of the last $retention day(s))..."
            while IFS= read -r line || [ -n "$line" ]; do
                timestamp=$(echo "$line" | $cmd_awk -F'[][]' '{print $2}')
                timestamp_seconds=$(date -d "$timestamp" +%s)
                difference=$(( (current_time - timestamp_seconds) / 86400 ))
                if (( $difference < $retention )); then
                    printf '%s\n' "$line" >> "$logFile.truncated"
                fi
            done < "$logFile"
            mv -f "$logFile.truncated" "$logFile"
            Write-Log "INFO" "    Pruning log file has been completed"
        else
            Write-Log "DEBUG" "    Pruning log file skipped"
        fi
    fi
}

Get-Path() {
    local name=$1

    if [ -x "/opt/bin/$name" ]; then
        echo "/opt/bin/$name"
        return
    fi

    if [ -x "/opt/sbin/$name" ]; then
        echo "/opt/sbin/$name"
        return
    fi

    local which_path=$(which $name 2>/dev/null | grep -v '^alias' 2>/dev/null)
    if [ -n "$which_path" ]; then
        echo "$which_path"
        return
    fi

    local whereis_path=$(whereis -b $name 2>/dev/null | gawk '{print $2}' 2>/dev/null)
    if [ -n "$whereis_path" ]; then
        echo "$whereis_path"
        return
    fi
}

Validate-ConfigFile() {
    Write-Log-Failed-To-Add-Some-Value() {
        Write-Log "ERROR" "    Failed to add value to \"$configFile\""
        End-Script 1
    }
    Write-To-ConfigFile() {
        local text_to_write=$1
        # local error_function
        echo "$text_to_write" >> $configFile 2>/dev/null || Write-Log-Failed-To-Add-Some-Value
    }
    local configFileFolder=$(dirname "$configFile")
    local validationError=false
    local rule_default_exists=false

    if ! test -f "$configFile"; then
        Write-Log "INFO" "    No configuration file found in \"$configFile\""
        Write-Log "INFO" "    Generating new configuration file..."

        mkdir -p $configFileFolder 2>/dev/null || { Write-Log "ERROR" "    Failed to create \"$configFileFolder\""; End-Script 1; }
        touch $configFile 2>/dev/null || { Write-Log "ERROR" "    Failed to create \"$configFile\""; End-Script 1; }
        chmod ugo+rw $configFile 2>/dev/null || { Write-Log "ERROR" "    Failed to modify permissions on \"$configFile\""; End-Script 1; }

        Write-To-ConfigFile "[general]"
        Write-To-ConfigFile "test_mode=${DCU_TEST_MODE:-"true"}"
        Write-To-ConfigFile "prune_images=${DCU_PRUNE_IMAGES:-"true"}"
        Write-To-ConfigFile "prune_container_backups=${DCU_PRUNE_CONTAINER_BACKUPS:-"true"}"
        Write-To-ConfigFile "container_backups_retention=${DCU_CONTAINER_BACKUPS_RETENTION:-"7"}"
        Write-To-ConfigFile "container_backups_keep_last=${DCU_CONTAINER_BACKUPS_KEEP_LAST:-"1"}"
        Write-To-ConfigFile "container_update_validation_time=${DCU_CONTAINER_UPDATE_VALIDATION_TIME:-"120"}"
        Write-To-ConfigFile "update_rules=${DCU_UPDATE_RULES:-"*[0.1.1-1,true]"}"
        Write-To-ConfigFile "docker_hub_api_url=${DCU_DOCKER_HUB_API_URL:-"https://registry.hub.docker.com/v2"}"
        Write-To-ConfigFile "github_container_repository_api_url=${DCU_GITHUB_CONTAINER_REPOSITORY_API_URL:-"https://ghcr.io/v2"}"
        Write-To-ConfigFile "docker_hub_api_image_tags_page_size_limit=${DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_SIZE_LIMIT:-"100"}"
        Write-To-ConfigFile "github_container_repository_api_image_tags_page_size_limit=${DCU_GITHUB_CONTAINER_REPOSITORY_API_IMAGE_TAGS_PAGE_SIZE_LIMIT:-"1000"}"
        Write-To-ConfigFile "docker_hub_api_image_tags_page_crawl_limit=${DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_CRAWL_LIMIT:-"10"}"
        Write-To-ConfigFile "github_container_repository_api_image_tags_page_crawl_limit=${DCU_GITHUB_CONTAINER_REPOSITORY_API_IMAGE_TAGS_PAGE_CRAWL_LIMIT:-"1000"}"
        Write-To-ConfigFile "docker_hub_image_minimum_age=${DCU_DOCKER_HUB_IMAGE_MINIMUM_AGE:-"21600"}"
        Write-To-ConfigFile "github_container_repository_image_minimum_age=${DCU_GITHUB_CONTAINER_REPOSITORY_IMAGE_MINIMUM_AGE:-"21600"}"
        Write-To-ConfigFile "pre_scripts_folder=${DCU_PRE_SCRIPTS_FOLDER:-"/usr/local/etc/container_update/pre-scripts"}"
        Write-To-ConfigFile "post_scripts_folder=${DCU_POST_SCRIPTS_FOLDER:-"/usr/local/etc/container_update/post-scripts"}"
        Write-To-ConfigFile ""
        Write-To-ConfigFile "[paths]"
        Write-To-ConfigFile "tput=$(Get-Path tput)"
        Write-To-ConfigFile "stty=$(Get-Path stty)"
        Write-To-ConfigFile "tee=$(Get-Path tee)"
        Write-To-ConfigFile "gawk=$(Get-Path gawk)"
        Write-To-ConfigFile "cut=$(Get-Path cut)"
        Write-To-ConfigFile "curl=$(Get-Path curl)"
        Write-To-ConfigFile "date=$(Get-Path date)"
        Write-To-ConfigFile "docker=$(Get-Path docker)"
        Write-To-ConfigFile "grep=$(Get-Path grep)"
        Write-To-ConfigFile "jq=$(Get-Path jq)"
        Write-To-ConfigFile "sed=$(Get-Path sed)"
        Write-To-ConfigFile "wget=$(Get-Path wget)"
        Write-To-ConfigFile "sort=$(Get-Path sort)"
        Write-To-ConfigFile "sendmail=$(Get-Path sendmail)"
        Write-To-ConfigFile ""
        Write-To-ConfigFile "[log]"
        Write-To-ConfigFile "filePath=${DCU_LOG_FILEPATH:-"/var/log/container_update.log"}"
        Write-To-ConfigFile "level=${DCU_LOG_LEVEL:-"INFO"}"
        Write-To-ConfigFile "retention=${DCU_LOG_RETENTION:-"7"}"
        Write-To-ConfigFile ""
        Write-To-ConfigFile "[mail]"
        Write-To-ConfigFile "notifications_enabled=${DCU_MAIL_NOTIFICATIONS_ENABLED:-"false"}"
        Write-To-ConfigFile "mode=${DCU_MAIL_NOTIFICATION_MODE:-"sendmail"}"
        Write-To-ConfigFile "from=${DCU_MAIL_FROM:-""}"
        Write-To-ConfigFile "recipients=${DCU_MAIL_RECIPIENTS:-""}"
        Write-To-ConfigFile "subject=${DCU_MAIL_SUBJECT:-"Docker Container Update Report from $(hostname)"}"
        Write-To-ConfigFile ""
        Write-To-ConfigFile "[telegram]"
        Write-To-ConfigFile "notifications_enabled=${DCU_TELEGRAM_NOTIFICATIONS_ENABLED:-"false"}"
        Write-To-ConfigFile "bot_token=${DCU_TELEGRAM_BOT_TOKEN:-""}"
        Write-To-ConfigFile "chat_id=${DCU_TELEGRAM_CHAT_ID:-""}"
        Write-To-ConfigFile "retry_interval=${DCU_TELEGRAM_RETRY_INTERVAL:-"10"}"
        Write-To-ConfigFile "retry_limit=${DCU_TELEGRAM_RETRY_LIMIT:-"2"}"
    else
        Write-Log "INFO" "    Existing configuration file found in \"$configFile\""

        # Update configuration file (add new attributes)
        if [ -z "$(Read-INI "$configFile" "general" "docker_hub_image_minimum_age")" ]; then
            Write-INI "$configFile" "general" "docker_hub_image_minimum_age" "21600"
        fi

        if [ -z "$(Read-INI "$configFile" "telegram" "notifications_enabled")" ]; then
            Write-INI "$configFile" "telegram" "retry_limit" "2"
            Write-INI "$configFile" "telegram" "retry_interval" "10"
            Write-INI "$configFile" "telegram" "bot_token" ""
            Write-INI "$configFile" "telegram" "chat_id" ""
            Write-INI "$configFile" "telegram" "notifications_enabled" "false"
        fi

        if [ -z "$(Read-INI "$configFile" "general" "github_container_repository_api_url")" ]; then
            Write-INI "$configFile" "general" "github_container_repository_api_url" "https://ghcr.io/v2"
            Write-INI "$configFile" "general" "github_container_repository_api_image_tags_page_size_limit" "1000"
            Write-INI "$configFile" "general" "github_container_repository_api_image_tags_page_crawl_limit" "10"
            Write-INI "$configFile" "general" "github_container_repository_image_minimum_age" "21600"
        fi
    fi

    Write-Log "INFO" "    Validating configuration file..."
    if [ $(Read-INI "$configFile" "general" "test_mode") != true ] && [ $(Read-INI "$configFile" "general" "test_mode") != false ]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] test_mode\" (Expected: \"true\" or \"false\")"
        validationError=true
    fi
    if [ $(Read-INI "$configFile" "general" "prune_images") != true ] && [ $(Read-INI "$configFile" "general" "prune_images") != false ]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] prune_images\" (Expected: \"true\" or \"false\")"
        validationError=true
    fi
    if [ $(Read-INI "$configFile" "general" "prune_container_backups") != true ] && [[ $(Read-INI "$configFile" "general" "prune_container_backups") != false ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] prune_container_backups\" (Expected: \"true\" or \"false\")"
        validationError=true
    fi
    if ! [[ $(Read-INI "$configFile" "general" "container_backups_retention") =~ ^[0-9]+$ ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] container_backups_retention\" (Expected: Type of \"integer\")"
        validationError=true
    fi
    if ! [[ $(Read-INI "$configFile" "general" "container_backups_keep_last") =~ ^[0-9]+$ ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] container_backups_keep_last\" (Expected: Type of \"integer\")"
        validationError=true
    fi
    if ! [[ $(Read-INI "$configFile" "general" "container_update_validation_time") =~ ^[0-9]+$ ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] container_update_validation_time\" (Expected: Type of \"integer\")"
        validationError=true
    fi
    if ! [[ $(Read-INI "$configFile" "general" "pre_scripts_folder") =~ ^/.* ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] pre_scripts_folder\" (Expected: Type of \"path\")"
    fi
    if ! [[ $(Read-INI "$configFile" "general" "post_scripts_folder") =~ ^/.* ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] post_scripts_folder\" (Expected: Type of \"path\")"
    fi

    IFS=' ' read -ra update_rules <<< "$(Read-INI "$configFile" "general" "update_rules")"
    if [ ${#update_rules[@]} -eq 0 ]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] update_rules\" (Expected: At least one rule)"
        validationError=true
    else
        local rule_regex='^(\*|[a-zA-Z_][a-zA-Z0-9_-]*)\[([0-9]+(&\(([Mmpb][><=][0-9]+[&|]?)+\))?[.]){2}([0-9]+(&\(([Mmpb][><=][0-9]+[&|]?)+\))?[-]){1}([0-9]+(&\(([Mmpb][><=][0-9]+[&|]?)+\))?[,]){1}(true|false)\]$'
        for update_rule in "${update_rules[@]}"; do
            if ! [[ "$update_rule" =~ $rule_regex ]]; then
                Write-Log "ERROR" "      => Invalid value in \"[general] update_rules\": Syntax validation error for the rule \"$update_rule\""
                validationError=true
            else
                Write-Log "DEBUG" "      => \"[general] update_rules\": The rule \"$update_rule\" matches the regex pattern for the rule syntax validation"
            fi

            if [[ "${update_rule:0:1}" == "*" ]]; then
                Write-Log "DEBUG" "      => \"[general] update_rules\": Found default rule \"$update_rule\""
                rule_default_exists=true
            fi
        done
    fi

    local url_regex='^(https?|ftp|file)://[-A-Za-z0-9\+&@#/%?=~_|!:,.;]*[-A-Za-z0-9\+&@#/%=~_|]\.[-A-Za-z0-9\+&@#/%?=~_|!:,.;]*[-A-Za-z0-9\+&@#/%=~_|]$'
    if ! [[ "$(Read-INI "$configFile" "general" "docker_hub_api_url")" =~ $url_regex ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] docker_hub_api_url\": \"$(Read-INI "$configFile" "general" "docker_hub_api_url")\" (Expected: Type of \"URL\")"
        validationError=true
    fi
    if ! [[ "$(Read-INI "$configFile" "general" "github_container_repository_api_url")" =~ $url_regex ]]; then
        Write-Log "WARNING" "      => Invalid value for \"[general] github_container_repository_api_url\": \"$(Read-INI "$configFile" "general" "github_container_repository_api_url")\" (Expected: Type of \"URL\")"
        validationError=false # Temporarily set to "false" due to a broken self-update mechanism in version 2024.11.08-2
    fi
    if ! [[ $(Read-INI "$configFile" "general" "docker_hub_api_image_tags_page_size_limit") =~ ^[0-9]+$ ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] docker_hub_api_image_tags_page_size_limit\" (Expected: Type of \"integer\")"
        validationError=true
    elif (( $(Read-INI "$configFile" "general" "docker_hub_api_image_tags_page_size_limit") <= 0 || $(Read-INI "$configFile" "general" "docker_hub_api_image_tags_page_size_limit") > 100 )); then
        Write-Log "ERROR" "      => Invalid value for \"[general] docker_hub_api_image_tags_page_size_limit\" (Min.: 1, Max.: 100, Current: $(Read-INI "$configFile" "general" "docker_hub_api_image_tags_page_size_limit"))"
        validationError=true
    fi
    if ! [[ $(Read-INI "$configFile" "general" "github_container_repository_api_image_tags_page_size_limit") =~ ^[0-9]+$ ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] github_container_repository_api_image_tags_page_size_limit\" (Expected: Type of \"integer\")"
        validationError=true
    elif (( $(Read-INI "$configFile" "general" "github_container_repository_api_image_tags_page_size_limit") <= 0 || $(Read-INI "$configFile" "general" "github_container_repository_api_image_tags_page_size_limit") > 1000 )); then
        Write-Log "ERROR" "      => Invalid value for \"[general] github_container_repository_api_image_tags_page_size_limit\" (Min.: 1, Max.: 1000, Current: $(Read-INI "$configFile" "general" "github_container_repository_api_image_tags_page_size_limit"))"
        validationError=true
    fi
    if ! [[ $(Read-INI "$configFile" "general" "docker_hub_api_image_tags_page_crawl_limit") =~ ^[0-9]+$ ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] docker_hub_api_image_tags_page_crawl_limit\" (Expected: Type of \"integer\")"
        validationError=true
    elif (( $(Read-INI "$configFile" "general" "docker_hub_api_image_tags_page_crawl_limit") <= 0 )); then
        Write-Log "ERROR" "      => Invalid value for \"[general] docker_hub_api_image_tags_page_crawl_limit\" (Min.: 1, Current: $(Read-INI "$configFile" "general" "docker_hub_api_image_tags_page_crawl_limit"))"
        validationError=true
    fi
    if ! [[ $(Read-INI "$configFile" "general" "github_container_repository_api_image_tags_page_crawl_limit") =~ ^[0-9]+$ ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] github_container_repository_api_image_tags_page_crawl_limit\" (Expected: Type of \"integer\")"
        validationError=true
    elif (( $(Read-INI "$configFile" "general" "github_container_repository_api_image_tags_page_crawl_limit") <= 0 )); then
        Write-Log "ERROR" "      => Invalid value for \"[general] github_container_repository_api_image_tags_page_crawl_limit\" (Min.: 1, Current: $(Read-INI "$configFile" "general" "github_container_repository_api_image_tags_page_crawl_limit"))"
        validationError=true
    fi
    if ! [[ $(Read-INI "$configFile" "general" "docker_hub_image_minimum_age") =~ ^[0-9]+$ ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] docker_hub_image_minimum_age\" (Expected: Type of \"integer\")"
        validationError=true
    elif (( $(Read-INI "$configFile" "general" "docker_hub_image_minimum_age") <= 0 )); then
        Write-Log "ERROR" "      => Invalid value for \"[general] docker_hub_image_minimum_age\" (Min.: 1, Current: $(Read-INI "$configFile" "general" "docker_hub_image_minimum_age"))"
        validationError=true
    fi
    if ! [[ $(Read-INI "$configFile" "general" "github_container_repository_image_minimum_age") =~ ^[0-9]+$ ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[general] github_container_repository_image_minimum_age\" (Expected: Type of \"integer\")"
        validationError=true
    elif (( $(Read-INI "$configFile" "general" "github_container_repository_image_minimum_age") <= 0 )); then
        Write-Log "ERROR" "      => Invalid value for \"[general] github_container_repository_image_minimum_age\" (Min.: 1, Current: $(Read-INI "$configFile" "general" "github_container_repository_image_minimum_age"))"
        validationError=true
    fi

    if ! [[ $(Read-INI "$configFile" "paths" "tput") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "tput" "$(Get-Path tput)"
        if ! [[ $(Read-INI "$configFile" "paths" "tput") =~ ^/.* ]]; then
            Write-Log "DEBUG"   "      => Invalid value for \"[paths] tput\" (Expected: Type of \"path\")"
        fi
    fi
    if ! [[ $(Read-INI "$configFile" "paths" "stty") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "stty" "$(Get-Path stty)"
        if ! [[ $(Read-INI "$configFile" "paths" "stty") =~ ^/.* ]]; then
            Write-Log "DEBUG"   "      => Invalid value for \"[paths] stty\" (Expected: Type of \"path\")"
        fi
    fi
    if ! [[ $(Read-INI "$configFile" "paths" "tee") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "tee" "$(Get-Path tee)"
        if ! [[ $(Read-INI "$configFile" "paths" "tee") =~ ^/.* ]]; then
            Write-Log "WARNING" "      => Invalid value for \"[paths] tee\" (Expected: Type of \"path\")"
        fi
    fi
    if ! [[ $(Read-INI "$configFile" "paths" "gawk") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "gawk" "$(Get-Path gawk)"
        if ! [[ $(Read-INI "$configFile" "paths" "gawk") =~ ^/.* ]]; then
            Write-Log "WARNING" "      => Invalid value for \"[paths] gawk\" (Expected: Type of \"path\")"
        fi
    fi
    if ! [[ $(Read-INI "$configFile" "paths" "cut") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "cut" "$(Get-Path cut)"
        if ! [[ $(Read-INI "$configFile" "paths" "cut") =~ ^/.* ]]; then
            Write-Log "WARNING" "      => Invalid value for \"[paths] cut\" (Expected: Type of \"path\")"
        fi
    fi
    if ! [[ $(Read-INI "$configFile" "paths" "curl") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "curl" "$(Get-Path curl)"
        if ! [[ $(Read-INI "$configFile" "paths" "curl") =~ ^/.* ]]; then
            Write-Log "WARNING" "      => Invalid value for \"[paths] curl\" (Expected: Type of \"path\")"
        fi
    fi
    if ! [[ $(Read-INI "$configFile" "paths" "date") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "date" "$(Get-Path date)"
        if ! [[ $(Read-INI "$configFile" "paths" "date") =~ ^/.* ]]; then
            Write-Log "WARNING" "      => Invalid value for \"[paths] date\" (Expected: Type of \"path\")"
        fi
    fi
    if ! [[ $(Read-INI "$configFile" "paths" "docker") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "docker" "$(Get-Path docker)"
        if ! [[ $(Read-INI "$configFile" "paths" "docker") =~ ^/.* ]]; then
            Write-Log "WARNING" "      => Invalid value for \"[paths] docker\" (Expected: Type of \"path\")"
        fi
    fi
    if ! [[ $(Read-INI "$configFile" "paths" "grep") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "grep" "$(Get-Path grep)"
        if ! [[ $(Read-INI "$configFile" "paths" "grep") =~ ^/.* ]]; then
            Write-Log "WARNING" "      => Invalid value for \"[paths] grep\" (Expected: Type of \"path\")"
        fi
    fi
    if ! [[ $(Read-INI "$configFile" "paths" "jq") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "jq" "$(Get-Path jq)"
        if ! [[ $(Read-INI "$configFile" "paths" "jq") =~ ^/.* ]]; then
            Write-Log "WARNING" "      => Invalid value for \"[paths] jq\" (Expected: Type of \"path\")"
        fi
    fi
    if ! [[ $(Read-INI "$configFile" "paths" "sed") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "sed" "$(Get-Path sed)"
        if ! [[ $(Read-INI "$configFile" "paths" "sed") =~ ^/.* ]]; then
            Write-Log "WARNING" "      => Invalid value for \"[paths] sed\" (Expected: Type of \"path\")"
        fi
    fi
    if ! [[ $(Read-INI "$configFile" "paths" "wget") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "wget" "$(Get-Path wget)"
        if ! [[ $(Read-INI "$configFile" "paths" "wget") =~ ^/.* ]]; then
            Write-Log "WARNING" "      => Invalid value for \"[paths] wget\" (Expected: Type of \"path\")"
        fi
    fi
    if ! [[ $(Read-INI "$configFile" "paths" "sort") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "sort" "$(Get-Path sort)"
        if ! [[ $(Read-INI "$configFile" "paths" "sort") =~ ^/.* ]]; then
            Write-Log "WARNING" "      => Invalid value for \"[paths] sort\" (Expected: Type of \"path\")"
        fi
    fi
    if [ "$(Read-INI "$configFile" "mail" "notifications_enabled")" == "true" ] && ! [[ $(Read-INI "$configFile" "paths" "sendmail") =~ ^/.* ]]; then
        Write-INI "$configFile" "paths" "sendmail" "$(Get-Path sendmail)"
        if [ "$(Read-INI "$configFile" "mail" "notifications_enabled")" == "true" ] && ! [[ $(Read-INI "$configFile" "paths" "sendmail") =~ ^/.* ]]; then
            Write-Log "WARNING" "      => Invalid value for \"[paths] sendmail\" (Expected: Type of \"path\")"
        fi
    fi

    if ! [[ $(Read-INI "$configFile" "log" "filePath") =~ ^/.* ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[log] filePath\" (Expected: Type of \"path\")"
        validationError=true
    fi
    if [ $(Read-INI "$configFile" "log" "level") != "DEBUG" ] && [ $(Read-INI "$configFile" "log" "level") != "INFO" ] && [ $(Read-INI "$configFile" "log" "level") != "WARNING" ] && [ $(Read-INI "$configFile" "log" "level") != "ERROR" ]; then
        Write-Log "ERROR" "      => Invalid value for \"[log] level\" (Expected: \"DEBUG\", \"INFO\", \"WARNING\", or \"ERROR\")"
        validationError=true
    fi
    if ! [[ $(Read-INI "$configFile" "log" "retention") =~ ^[0-9]+$ ]]; then
        Write-Log "ERROR" "      => Invalid value for \"[log] retention\" (Expected: Type of \"integer\")"
        validationError=true
    fi

    if [ "$(Read-INI "$configFile" "mail" "notifications_enabled")" != "true" ] && [ "$(Read-INI "$configFile" "mail" "notifications_enabled")" != "false" ]; then
        Write-Log "ERROR" "      => Invalid value for \"[mail] notifications_enabled\" (Expected: \"true\" or \"false\")"
        validationError=true
    fi
    if [ "$(Read-INI "$configFile" "mail" "notifications_enabled")" == "true" ] && [ "$(Read-INI "$configFile" "mail" "mode")" != "sendmail" ]; then
        Write-Log "ERROR" "      => Invalid value for \"[mail] mode\" (Expected: \"sendmail\")"
        validationError=true
    fi
    if [[ "$(Read-INI "$configFile" "mail" "notifications_enabled")" == "true" && ! $(Read-INI "$configFile" "mail" "from") =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        Write-Log "WARNING" "      => Invalid value for \"[mail] from\" (Expected: Type of \"email\")"
    fi
    if [[ "$(Read-INI "$configFile" "mail" "notifications_enabled")" == "true" && ! $(Read-INI "$configFile" "mail" "recipients") =~ ^([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})([[:space:]]*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})*$ ]]; then
        Write-Log "WARNING" "      => Invalid value for \"[mail] recipients\" (Expected: One or multiple E-Mail addresses seperated by spaces)"
    fi
    if [[ "$(Read-INI "$configFile" "mail" "notifications_enabled")" == "true" && -z $(Read-INI "$configFile" "mail" "subject") ]]; then
        Write-Log "WARNING" "      => Empty value for \"[mail] subject\""
    fi

    if [ "$(Read-INI "$configFile" "telegram" "notifications_enabled")" != "true" ] && [ "$(Read-INI "$configFile" "telegram" "notifications_enabled")" != "false" ]; then
        Write-Log "ERROR" "      => Invalid value for \"[telegram] notifications_enabled\" (Expected: \"true\" or \"false\")"
        validationError=true
    fi
    if [ "$(Read-INI "$configFile" "telegram" "notifications_enabled")" == "true" ] && [ -z "$(Read-INI "$configFile" "telegram" "bot_token")" ]; then
        Write-Log "ERROR" "      => Empty value for \"[telegram] bot_token\""
        validationError=true
    fi
    if [ "$(Read-INI "$configFile" "telegram" "notifications_enabled")" == "true" ] && [ -z "$(Read-INI "$configFile" "telegram" "chat_id")" ]; then
        Write-Log "WARNING" "      => Empty value for \"[telegram] chat_id\""
        validationError=true
    fi
    if [[ "$(Read-INI "$configFile" "telegram" "notifications_enabled")" == "true" && ! $(Read-INI "$configFile" "telegram" "retry_interval") =~ ^[0-9]+$ ]]; then
        Write-Log "WARNING" "      => Invalid value for \"[telegram] retry_interval\" (Expected: Type of \"integer\")"
        validationError=true
    fi
    if [[ "$(Read-INI "$configFile" "telegram" "notifications_enabled")" == "true" && ! $(Read-INI "$configFile" "telegram" "retry_limit") =~ ^[0-9]+$ ]]; then
        Write-Log "WARNING" "      => Invalid value for \"[telegram] retry_limit\" (Expected: Type of \"integer\")"
        validationError=true
    fi

    if [ $rule_default_exists == false ]; then
        Write-Log "ERROR" "      => Invalid value in \"[general] update_rules\": The default rule is mandatory"
        validationError=true
    fi

    if [ $validationError == true ]; then
        End-Script 1
    fi
}

Test-Prerequisites() {
    local versionInstalled=""
    local command=""
    local validationError=false

    Write-Log "INFO" "    Checking your system and testing prerequisites..."

    command="bash"
    versionInstalled=$("$command" --version | head -n 1)
    Write-Log "DEBUG" "      => Your \"$command\" is available in version \"$versionInstalled\""

    # QNAP specific \
        if [[ "$versionInstalled" =~ "QNAP" ]]; then
            if [ -z "$(Read-INI "$configFile" "qnap_systems" "mandatory_packages_install")" ]; then
                echo "                                  ------------------------------------------------------------------------------------------------------------------------------"
                echo "                                  QNAP SYSTEM DETECTED!"
                echo "                                  ------------------------------------------------------------------------------------------------------------------------------"
                echo "                                  On QNAP systems, additional packages are required to make this script work."
                echo "                                  You can choose to install these packages manually or let this script handle the installation automatically when executed."
                echo "                                  If you opt for manual installation, remember that after each restart of your QNAP, these packages will be removed by default."
                echo "                                      - coreutils-sort"
                echo "                                      - coreutils-cut"
                echo "                                      - coreutils-date"
                echo "                                      - grep"
                echo "                                      - jq"
                echo "                                      - sed"
                echo "                                      - wget"
                echo "                                      - gawk"
                read -p "                                  Would you like this script to automatically install the mandatory components every time it runs via entware-ng repository? (yes/no) [Default: no]: " response

                if [ -z "$response" ] || [ "$response" != "yes" ] && [ "$response" != "y" ]; then
                    Write-Log "INFO" "    You chose not to install components automatically"
                    Write-Log "INFO" "    You can change this behavior in your configuration file \"$configFile\""
                    Write-INI "$configFile" "qnap_systems" "mandatory_packages_install" "manual"
                else
                    Write-INI "$configFile" "qnap_systems" "mandatory_packages_install" "auto"
                fi
            fi
        fi

        if [ "$(Read-INI "$configFile" "qnap_systems" "mandatory_packages_install")" == "auto" ]; then
            Write-Log "INFO" "         Installing additional packages via entware-ng..."
            wget -O - http://pkg.entware.net/binaries/x86-64/installer/entware_install.sh 2>/dev/null | /bin/sh >/dev/null 2>&1
            /opt/bin/opkg update >/dev/null 2>&1
            /opt/bin/opkg install coreutils-sort >/dev/null 2>&1
            /opt/bin/opkg install coreutils-cut >/dev/null 2>&1
            /opt/bin/opkg install coreutils-date >/dev/null 2>&1
            /opt/bin/opkg install grep >/dev/null 2>&1
            /opt/bin/opkg install jq >/dev/null 2>&1
            /opt/bin/opkg install sed >/dev/null 2>&1
            /opt/bin/opkg install wget >/dev/null 2>&1
            /opt/bin/opkg install gawk >/dev/null 2>&1
        fi
    # QNAP specific /

    command="tput"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=false
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" -V 2>/dev/null | head -n 1)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "DEBUG" "      => It seems there is no version of \"$command\" installed on your system"
    fi

    command="stty"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=false
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" --version 2>/dev/null | head -n 1)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "DEBUG" "      => It seems there is no version of \"$command\" installed on your system"
    fi

    command="tee"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=true
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" -V 2>/dev/null | head -n 1)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "WARNING" "      => It seems there is no version of \"$command\" installed on your system"
    fi

    command="gawk"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=true
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" --version 2>/dev/null | head -n 1)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "ERROR" "      => It seems there is no version of \"$command\" installed on your system"
        validationError=true
    fi

    command="cut"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=true
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" --version 2>/dev/null | head -n 1)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "ERROR" "      => It seems there is no version of \"$command\" installed on your system"
        validationError=true
    fi

    command="curl"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=true
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" --version 2>/dev/null | head -n 1)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "ERROR" "      => It seems there is no version of \"$command\" installed on your system"
        validationError=true
    fi

    command="date"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=true
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" --version 2>/dev/null | head -n 1)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "ERROR" "      => It seems there is no version of \"$command\" installed on your system"
        validationError=true
    fi

    command="docker"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=true
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" --version 2>/dev/null)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "ERROR" "      => It seems there is no version of \"$command\" installed on your system"
        validationError=true
    fi

    command="grep"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=true
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" --version 2>/dev/null | head -n 1)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "ERROR" "      => It seems there is no version of \"$command\" installed on your system"
        validationError=true
    fi

    command="jq"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=true
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" --version 2>/dev/null)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "ERROR" "      => It seems there is no version of \"$command\" installed on your system"
        validationError=true
    fi

    command="sed"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=true
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" --version 2>/dev/null | head -n 1)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "ERROR" "      => It seems there is no version of \"$command\" installed on your system"
        validationError=true
    fi

    command="wget"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=true
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" --version 2>/dev/null | head -n 1)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "ERROR" "      => It seems there is no version of \"$command\" installed on your system"
        validationError=true
    fi

    command="sort"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "ERROR" "      => Could not find \"$command\""
            validationError=true
        else
            versionInstalled=$("$(Read-INI "$configFile" "paths" "$command")" --version 2>/dev/null | head -n 1)
            Write-Log "DEBUG" "      => Found \"$command\" installed in version \"$versionInstalled\""
        fi
    else
        Write-Log "ERROR" "      => It seems there is no version of \"$command\" installed on your system"
        validationError=true
    fi

    command="sendmail"
    if [ -n "$(Read-INI "$configFile" "paths" "$command")" ]; then
        if ! [ -x "$(Read-INI "$configFile" "paths" "$command")" ]; then
            Write-Log "WARNING" "      => Could not find \"$command\""
        else
            Write-Log "DEBUG" "      => Found \"$command\""
        fi
    elif [ "$(Read-INI "$configFile" "mail" "notifications_enabled")" == "true" ]; then
        Write-Log "WARNING" "      => It seems there is no version of \"$command\" installed on your system"
    fi

    if [ $validationError == true ]; then
        Write-Log "ERROR" "Insufficient system requirements detected"
        End-Script 1
    fi
}

Get-ScriptVersion() {
    local cmd_cut=$(Read-INI "$configFile" "paths" "cut" 2>/dev/null); cmd_cut=${cmd_cut:-cut}
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed" 2>/dev/null); cmd_sed=${cmd_sed:-sed}
    local cmd_grep=$(Read-INI "$configFile" "paths" "grep" 2>/dev/null); cmd_grep=${cmd_grep:-grep}

    local version_line=$(head -n 10 "$0" | $cmd_grep -n "# ## Version" | $cmd_cut -d: -f1)
    local next_line=0

    if [ -n "$version_line" ]; then
        next_line=$((version_line + 1))
        $cmd_sed "${next_line}q;d" "$0" | $cmd_cut -d " " -f2
    else
        echo "Not found"
    fi
}

Get-ContainerProperty() {
    local container_config=$1
    local property=$2
    local cmd_awk=$(Read-INI "$configFile" "paths" "gawk")
    local cmd_cut=$(Read-INI "$configFile" "paths" "cut")
    local cmd_jq=$(Read-INI "$configFile" "paths" "jq")
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed")

    if ! $cmd_jq -e . >/dev/null 2>&1 <<<"$container_config"; then
        Write-Log "ERROR" "Invalid json data passed to \"Get-ContainerProperty()\""
        return
    fi

    if   [ "$property" == "container_name" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].Name' | $cmd_sed 's#^/##' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_hostname" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].Config.Hostname' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_state_paused" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].State.Paused' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_labels" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].Config.Labels | to_entries[] | "--label \"\(.key)=\(.value)\""' 2>/dev/null | tr '\n' ' ' | $cmd_sed 's/^null$//' | $cmd_sed 's/`/\\`/g')"
        return
    elif [ "$property" == "container_capabilities" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].HostConfig.CapAdd[]' 2>/dev/null | $cmd_sed 's/^/--cap-add=/' | tr '\n' ' ' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_networkMode" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].HostConfig.NetworkMode' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_networkMode_IPv4Address" ]; then
        #echo "$(echo "$container_config" | $cmd_jq -r '.[0].NetworkSettings.Networks | .[] | .IPAMConfig.IPv4Address' | $cmd_sed 's/^null$//')"
        #echo "$(echo "$container_config" | $cmd_jq -r '.[0].NetworkSettings.Networks['\"$(echo "$container_config" | $cmd_jq -r '.[0].HostConfig.NetworkMode' | $cmd_sed 's/^null$//')\"'].IPAMConfig.IPv4Address' | $cmd_sed 's/^null$//')"
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].NetworkSettings.Networks['\"$(Get-ContainerProperty "$container_config" "container_networkMode")\"'].IPAMConfig.IPv4Address' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_networkMode_IPv6Address" ]; then
        #echo "$(echo "$container_config" | $cmd_jq -r '.[0].NetworkSettings.Networks | .[] | .IPAMConfig.IPv6Address' | $cmd_sed 's/^null$//')"
        #echo "$(echo "$container_config" | $cmd_jq -r '.[0].NetworkSettings.Networks['\"$(echo "$container_config" | $cmd_jq -r '.[0].HostConfig.NetworkMode' | $cmd_sed 's/^null$//')\"'].IPAMConfig.IPv6Address' | $cmd_sed 's/^null$//')"
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].NetworkSettings.Networks['\"$(Get-ContainerProperty "$container_config" "container_networkMode")\"'].IPAMConfig.IPv6Address' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_networkMode_MacAddress" ]; then
        #echo "$(echo "$container_config" | $cmd_jq -r '.[0].NetworkSettings.Networks | .[] | .MacAddress' | $cmd_sed 's/^null$//')"
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].NetworkSettings.Networks['\"$(echo "$container_config" | $cmd_jq -r '.[0].HostConfig.NetworkMode' | $cmd_sed 's/^null$//')\"'].MacAddress' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_primaryNetwork_Name" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].NetworkSettings.Networks | keys_unsorted[]' | head -n 1 | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_primaryNetwork_IPv4Address" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].NetworkSettings.Networks | .[] | .IPAMConfig.IPv4Address' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_primaryNetwork_IPv6Address" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].NetworkSettings.Networks | .[] | .IPAMConfig.IPv6Address' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_primaryNetwork_MacAddress" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].NetworkSettings.Networks | .[] | .MacAddress' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_restartPolicy_name" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].HostConfig.RestartPolicy.Name' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_restartPolicy_MaximumRetryCount" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].HostConfig.RestartPolicy.MaximumRetryCount' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_PublishAllPorts" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].HostConfig.PublishAllPorts' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_Privileged" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].HostConfig.Privileged' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_Tty" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].Config.Tty' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_PortBindings" ]; then
        local PortBindings=$(echo "$container_config" | $cmd_jq -r '.[0].HostConfig.PortBindings')
        local PortBindings_count=$(echo "$PortBindings" | $cmd_jq '. | length')
        local host_port_key_name=""
        local host_port=""
        local protocol=""
        local container_port=""
        local PortBindings_sting=""

        if [ "$PortBindings_count" -gt 0 ] && [ -n "$PortBindings_count" ]; then
            for ((i = 0; i < PortBindings_count; i++)); do
                host_port_key_name=$(echo "$PortBindings" | $cmd_jq -r ". | keys_unsorted | .[$i]")
                if [[ $host_port_key_name == */* ]]; then
                    host_port=$(echo "$host_port_key_name" | $cmd_cut -d'/' -f1)
                    protocol=$(echo "$host_port_key_name" | $cmd_cut -d'/' -f2)
                else
                    host_port=$host_port_key_name
                    protocol=""
                fi
                container_port=$(echo "$PortBindings" | $cmd_jq -r ".[\"$host_port_key_name\"][0].HostPort")
                PortBindings_sting+=" --publish $container_port:$host_port"
            done
        fi

        echo "$(echo "$PortBindings_sting" | $cmd_sed -e 's/^[[:space:]]*//' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_Mounts" ]; then
        local mounts=$(echo "$container_config" | $cmd_jq -r '.[0].Mounts')
        local mounts_count=$(echo "$mounts" | $cmd_jq '. | length')
        local mounts_string=""
        local mount_destination=""
        local mount_driver=""
        local mount_mode=""
        local mount_propagation=""
        local mount_rw=""
        local mount_source=""
        local mount_type=""

        if [ "$mounts_count" -gt 0 ] && [ -n "$mounts_count" ]; then
            for ((i = 0; i < mounts_count; i++)); do
                mount_destination=$(echo "$mounts" | $cmd_jq -r ".[$i].Destination" | $cmd_sed 's/ /\\ /g')
                mount_driver=$(echo "$mounts" | $cmd_jq -r ".[$i].Driver" | $cmd_sed 's/ /\\ /g')
                mount_mode=$(echo "$mounts" | $cmd_jq -r ".[$i].Mode" | $cmd_sed 's/ /\\ /g')
                mount_propagation=$(echo "$mounts" | $cmd_jq -r ".[$i].Propagation" | $cmd_sed 's/ /\\ /g')
                mount_rw=$(echo "$mounts" | $cmd_jq -r ".[$i].RW" | $cmd_sed 's/ /\\ /g')
                mount_source=$(echo "$mounts" | $cmd_jq -r ".[$i].Source" | $cmd_sed 's/ /\\ /g')
                mount_type=$(echo "$mounts" | $cmd_jq -r ".[$i].Type")

                if [ -z "$mount_driver" ] || [ "$mount_driver" == "null" ] || [ "$mount_driver" == "" ]; then
                    # Only add non-auto-generated / persistent / user-defined mounts
                    mounts_string+=" --mount "
                    [ -n "$mount_type" ]        && mounts_string+="type=$mount_type"
                    [ -n "$mount_source" ]      && mounts_string+=",source=$mount_source"
                    [ -n "$mount_destination" ] && mounts_string+=",target=$mount_destination"
                    [ "$mount_rw" == "false" ]  && mounts_string+=",readonly"
                fi
            done
        fi

        echo "$(echo "$mounts_string" | $cmd_sed -e 's/^[[:space:]]*//' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_envs" ]; then
        local envs=$(echo "$container_config" | $cmd_jq -r '.[0].Config.Env')
        local envs_count=$(echo "$envs" | $cmd_jq '. | length')
        local env=""
        local env_name=""
        local env_value=""
        local envs_sting=""

        if [ "$envs_count" -gt 0 ] && [ -n "$envs_count" ]; then
            for ((i = 0; i < envs_count; i++)); do
                env=$(echo "$envs" | $cmd_jq -r ".[$i]")
                env_name="${env%%=*}"
                env_value="${env#*=}"
                #envs_sting+=" --env $env_name='$env_value'"
                envs_sting+=" --env $env_name=\"$env_value\""
            done
        fi

        echo "$(echo "$envs_sting" | $cmd_sed -e 's/^[[:space:]]*//' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_tmpfs" ]; then
        local tmpfs=$(echo "$container_config" | $cmd_jq -r '.[0].HostConfig.Tmpfs' | $cmd_sed 's/^null$//')
        local tmpfs_values=""
        local tmpfs_sting=""

        if [ -n "$tmpfs" ]; then
            tmpfs_values=($(echo "$container_config" | $cmd_jq -r '.[0].HostConfig.Tmpfs | to_entries[] | .key + ":" + .value'))
            for value in "${tmpfs_values[@]}"; do
                tmpfs_sting+=" --tmpfs $value"
            done
        fi

        echo "$(echo "$tmpfs_sting" | $cmd_sed -e 's/^[[:space:]]*//' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_cmd" ]; then
        local cmds=$(echo "$container_config" | $cmd_jq -r '.[0].Config.Cmd')
        local cmds_count=$(echo "$cmds" | $cmd_jq '. | length')
        local cmd=""
        local cmds_sting=""

        if [ "$cmds_count" -gt 0 ] && [ -n "$cmds_count" ]; then
            for ((i = 0; i < cmds_count; i++)); do
                cmd=$(echo "$cmds" | $cmd_jq -r ".[$i]")
                cmds_sting+=" $cmd"
            done
        fi

        echo "$(echo "$cmds_sting" | $cmd_sed -e 's/^[[:space:]]*//' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_image_id" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].Image' | $cmd_sed 's#^/##' | $cmd_awk -F: '{print $2}' | $cmd_cut -b 1-13 | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_image_name" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].Config.Image' | $cmd_cut -d':' -f1 | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "container_image_tag" ]; then
        echo "$(echo "$container_config" | $cmd_jq -r '.[0].Config.Image' | $cmd_cut -d':' -f2 | $cmd_sed 's/^null$//')"
        return
    else
        Write-Log "ERROR" "Unknown property requested: $property"
    fi
}

Get-ImageProperty() {
    local image_config=$1
    local property=$2
    local cmd_awk=$(Read-INI "$configFile" "paths" "gawk")
    local cmd_cut=$(Read-INI "$configFile" "paths" "cut")
    local cmd_jq=$(Read-INI "$configFile" "paths" "jq")
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed")

    if ! $cmd_jq -e . >/dev/null 2>&1 <<<"$image_config"; then
        Write-Log "ERROR" "Invalid json data passed to \"Get-ImageProperty()\""
        return
    fi

    if   [ "$property" == "image_repoDigests" ]; then
        local digests=$(echo "$image_config" | $cmd_jq -r '.[0].RepoDigests')
        local digests_count=$(echo "$digests" | $cmd_jq '. | length')
        local digest=""
        local digests_sting=""

        if [ "$digests_count" -gt 0 ] && [ -n "$digests_count" ]; then
            for ((i = 0; i < digests_count; i++)); do
                digest=$(echo "$digests" | $cmd_jq -r ".[$i]" | $cmd_cut -d':' -f2)
                digests_sting+=" $digest"
            done
        fi

        echo "$(echo "$digests_sting" | $cmd_sed -e 's/^[[:space:]]*//' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "image_labels" ]; then
        echo "$(echo "$image_config" | $cmd_jq -r '.[0].Config.Labels | to_entries[] | "--label \"\(.key)=\(.value)\""' 2>/dev/null | tr '\n' ' ' | $cmd_sed 's/^null$//' | $cmd_sed 's/`/\\`/g')"
        return
    elif [ "$property" == "image_envs" ]; then
        local envs=$(echo "$image_config" | $cmd_jq -r '.[0].Config.Env')
        local envs_count=$(echo "$envs" | $cmd_jq '. | length')
        local env=""
        local env_name=""
        local env_value=""
        local envs_sting=""

        if [ "$envs_count" -gt 0 ] && [ -n "$envs_count" ]; then
            for ((i = 0; i < envs_count; i++)); do
                env=$(echo "$envs" | $cmd_jq -r ".[$i]")
                env_name="${env%%=*}"
                env_value="${env#*=}"
                #envs_sting+=" --env $env_name='$env_value'"
                envs_sting+=" --env $env_name=\"$env_value\""
            done
        fi

        echo "$(echo "$envs_sting" | $cmd_sed -e 's/^[[:space:]]*//' | $cmd_sed 's/^null$//')"
        return
    elif [ "$property" == "image_cmd" ]; then
        local cmds=$(echo "$image_config" | $cmd_jq -r '.[0].Config.Cmd')
        local cmds_count=$(echo "$cmds" | $cmd_jq '. | length')
        local cmd=""
        local cmds_sting=""

        if [ "$cmds_count" -gt 0 ] && [ -n "$cmds_count" ]; then
            for ((i = 0; i < cmds_count; i++)); do
                cmd=$(echo "$cmds" | $cmd_jq -r ".[$i]")
                cmds_sting+=" $cmd"
            done
        fi

        echo "$(echo "$cmds_sting" | $cmd_sed -e 's/^[[:space:]]*//' | $cmd_sed 's/^null$//')"
        return
    else
        Write-Log "ERROR" "Unknown property requested: $property"
    fi
}

Get-ContainerPropertyUnique() {
    #############################
    ## This function compares some container properties with the default properties of the original image and gives back a string with a delta
    #############################
    local value_container=$1
    local value_image=$2
    local property=$3
    local cmd_awk=$(Read-INI "$configFile" "paths" "gawk")
    local cmd_cut=$(Read-INI "$configFile" "paths" "cut")
    local cmd_jq=$(Read-INI "$configFile" "paths" "jq")
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed")

    if   [ "$property" == "unique_labels" ]; then
        local container_labels_seperated=$(echo "$value_container" | $cmd_sed 's/--label /\n/g')
        local image_labels_seperated=$(echo "$value_image" | $cmd_sed 's/--label /\n/g')

        IFS=$'\n' read -rd '' -a container_labels_array <<<"$container_labels_seperated"
        IFS=$'\n' read -rd '' -a image_labels_array <<<"$image_labels_seperated"
        for container_label in "${container_labels_array[@]}"; do
            local container_label_name=$(echo "$container_label" | $cmd_cut -d= -f1 | $cmd_sed 's/^"\(.*\)/\1/')
            #local container_label_value=$(echo "$container_label" | $cmd_cut -d= -f2 | $cmd_sed 's/\(.*\)" $/\1/') # In case the label value has a '='-Sign in it, this causes an issue
            local container_label_value=$(echo "$container_label" | $cmd_sed 's/^[^=]*=//' | $cmd_sed 's/\(.*\)" $/\1/')
            local container_label_name_isUnique=true

            for image_label in "${image_labels_array[@]}"; do
                local image_label_name=$(echo "$image_label" | $cmd_cut -d= -f1 | $cmd_sed 's/^"\(.*\)/\1/')
                local image_label_value=$(echo "$image_label" | $cmd_cut -d= -f2 | $cmd_sed 's/\(.*\)" $/\1/')

                if [ "$image_label_name" == "$container_label_name" ]; then
                    container_label_name_isUnique=false
                    break
                fi
            done

            if [ "$container_label_name_isUnique" == true ]; then
                unique_labels+="--label \"$container_label_name=$container_label_value\" "
            fi
        done

        unique_labels=$(echo "$unique_labels" | $cmd_sed 's/\(.*\) $/\1/')

        echo "$unique_labels"
        return
    elif [ "$property" == "unique_envs" ]; then
        local container_variables_seperated=$(echo "$value_container" | $cmd_sed 's/--env /\n/g')
        local image_variables_seperated=$(echo "$value_image" | $cmd_sed 's/--env /\n/g')

        IFS=$'\n' read -rd '' -a container_variables_array <<<"$container_variables_seperated"
        IFS=$'\n' read -rd '' -a image_variables_array <<<"$image_variables_seperated"
        for container_variable in "${container_variables_array[@]}"; do
            local container_variable_name=$(echo "$container_variable" | $cmd_cut -d= -f1 | $cmd_sed 's/^"\(.*\)/\1/')
            # local container_variable_value=$(echo "$container_variable" | $cmd_cut -d= -f2 | $cmd_sed 's/ *"$//') # In case the variable value has a '='-Sign in it, this causes an issue
            local container_variable_value=$(echo "$container_variable" | $cmd_sed 's/^[^=]*=//' | $cmd_sed 's/ *"$/"/')
            local container_variable_name_isUnique=true

            for image_variable in "${image_variables_array[@]}"; do
                local image_variable_name=$(echo "$image_variable" | $cmd_cut -d= -f1 | $cmd_sed 's/^"\(.*\)/\1/')
                local image_variable_value=$(echo "$image_variable" | $cmd_sed 's/^[^=]*=//' | $cmd_sed 's/ *"$/"/')

                if [ "$image_variable_name" == "$container_variable_name" ]; then
                    container_variable_name_isUnique=false
                    break
                fi
            done

            if [ "$container_variable_name_isUnique" == true ]; then
                unique_variables+="--env $container_variable_name=$container_variable_value"
            fi
        done

        unique_variables=$(echo "$unique_variables" | $cmd_sed 's/\(.*\) $/\1/')

        echo "$unique_variables"
        return
    else
        Write-Log "ERROR" "Unknown property requested: $property"
    fi
}

New-DockerHubImageTagFilter() {
    local template="$1"
    local group=$2
    local regexFilter=""
    local cmd_cut=$(Read-INI "$configFile" "paths" "cut")
    local i=0
    local seperator_count=0
    local seperator_count_max=0

    if   [ "$group" == "by_major" ]; then
        seperator_count_max=1
    elif [ "$group" == "by_minor" ]; then
        seperator_count_max=2
    elif [ "$group" == "by_patch" ]; then
        seperator_count_max=3
    elif [ "$group" == "by_build" ]; then
        seperator_count_max=4
    fi

    if [ -n "$group" ]; then
        for ((i=$i; i<${#template}; i++)); do
            char="${template:$i:1}"
            if [[ "$char" == "." || "$char" == "-" ]]; then
                (( seperator_count++ ))
                if (( seperator_count == seperator_count_max )); then
                    break
                fi
            fi
            regexFilter+="${char}"
        done
    fi

    for ((i=$i; i<${#template}; i++)); do
        char="${template:$i:1}"
        if [[ "$char" =~ [0-9] ]]; then
            if [[ "$last_char_type" != "integer" ]]; then
                regexFilter="${regexFilter}[0-9]+"
                last_char_type="integer"
            fi
        else
            regexFilter="${regexFilter}${char}"
            last_char_type="string"
        fi
    done

    echo "^$regexFilter$"
    return
}

Extract-VersionPart() {
    local template=$1
    local version=$2
    local cmd_cut=$(Read-INI "$configFile" "paths" "cut")
    local cmd_grep=$(Read-INI "$configFile" "paths" "grep")
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed")
    local template_extraDotsRemoved=""
    local dot_count=0

    # Replace all dashes with dots
    template=$(echo "$template" | $cmd_sed 's/-/./g' )

    # Remove all characters except '0-9' and '.'
    template=$(echo "$template" | tr -dc '0-9.')

    # Replace multiple consecutive dots with a single dot
    while [[ "$template" == *..* ]]; do
        template="${template//../.}"
    done

    # Remove all dots after the fourth
    for (( i=0; i<${#template}; i++ )); do
        char="${template:$i:1}"
        if [[ "$char" == "." ]]; then
            dot_count=$((dot_count + 1))
            if [[ $dot_count -lt 4 ]]; then
                template_extraDotsRemoved+="$char"
            fi
        else
            template_extraDotsRemoved+="$char"
        fi
    done
    template="$template_extraDotsRemoved"

    # Remove leading and trailing dots
    template=$(echo "$template" | $cmd_sed 's/^\.//;s/\.$//')

    if   [ -n "$template" ] && [ "$version" == "major" ]; then
        VersionPart=$(echo "$template" | $cmd_cut -d'.' -f1)
        if [[ "$VersionPart" =~ ^[0-9]+$ ]]; then
            echo "$((10#$VersionPart))" # Remove leading zeros and extract the part before the first dot
        else
            echo $VersionPart
        fi
        return
    elif [ -n "$template" ] && [ "$version" == "minor" ]; then
        VersionPart=$(echo "$template" | $cmd_cut -d'.' -f2)
        if [[ "$VersionPart" =~ ^[0-9]+$ ]]; then
            echo "$((10#$VersionPart))" # Remove leading zeros and extract the part before the first dot
        else
            echo $VersionPart
        fi
        return
    elif [ -n "$template" ] && [ "$version" == "patch" ]; then
        VersionPart=$(echo "$template" | $cmd_cut -d'.' -f3)
        if [[ "$VersionPart" =~ ^[0-9]+$ ]]; then
            echo "$((10#$VersionPart))" # Remove leading zeros and extract the part before the first dot
        else
            echo $VersionPart
        fi
        return
    elif [ -n "$template" ] && [ "$version" == "build" ]; then
        VersionPart=$(echo "$template" | $cmd_cut -d'.' -f4)
        if [[ "$VersionPart" =~ ^[0-9]+$ ]]; then
            echo "$((10#$VersionPart))" # Remove leading zeros and extract the part before the first dot
        else
            echo $VersionPart
        fi
        return
    # else
    #     Write-Log "ERROR" "Unknown version type requested: $version"
    fi

    echo "$template"
}

Get-EffectiveUpdateRule() {
    local container_name=$1
    local cmd_grep=$(Read-INI "$configFile" "paths" "grep")
    local update_rule_name=""

    IFS=' ' read -ra update_rules <<< "$(Read-INI "$configFile" "general" "update_rules")"
    for update_rule in "${update_rules[@]}"; do
        update_rule_name=$(echo "$update_rule" | $cmd_grep -o '^[^[]*')
        if [ "$update_rule_name" == "$container_name" ]; then
            effective_update_rule=$update_rule
        elif [ "$update_rule_name" == "*" ]; then
            default_update_rule=$update_rule
        fi
    done
    [ -z "$effective_update_rule" ] && effective_update_rule=$default_update_rule

    echo "$effective_update_rule"
    return
}

Get-UpdatePermit() {
    local container_name=$1
    local image_tag_name_current=$2
    local image_tag_name_next=$3
    local image_tag_name_latest_related=$4
    local cmd_awk=$(Read-INI "$configFile" "paths" "gawk")
    local cmd_cut=$(Read-INI "$configFile" "paths" "cut")
    local cmd_grep=$(Read-INI "$configFile" "paths" "grep")
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed")
    local effective_update_rule="$(Get-EffectiveUpdateRule "container_name")"
    local compare_operator=""
    local compare_val=""
    local rule_major=$(echo "$effective_update_rule" | $cmd_cut -d '[' -f2 | $cmd_cut -d '.' -f1)
    local rule_minor=$(echo "$effective_update_rule" | $cmd_cut -d '[' -f2 | $cmd_cut -d '.' -f2)
    local rule_patch=$(echo "$effective_update_rule" | $cmd_cut -d '[' -f2 | $cmd_cut -d '.' -f3 | $cmd_cut -d '-' -f1)
    local rule_build=$(echo "$effective_update_rule" | $cmd_cut -d '-' -f2 | $cmd_cut -d ',' -f1)
    local rule_digests=$(echo "$effective_update_rule" | $cmd_cut -d ',' -f2 | $cmd_cut -d ']' -f1)
    local major_current=$(Extract-VersionPart "$image_tag_name_current" "major")
    local minor_current=$(Extract-VersionPart "$image_tag_name_current" "minor")
    local patch_current=$(Extract-VersionPart "$image_tag_name_current" "patch")
    local build_current=$(Extract-VersionPart "$image_tag_name_current" "build")
    local major_next=$(Extract-VersionPart "$image_tag_name_next" "major")
    local minor_next=$(Extract-VersionPart "$image_tag_name_next" "minor")
    local patch_next=$(Extract-VersionPart "$image_tag_name_next" "patch")
    local build_next=$(Extract-VersionPart "$image_tag_name_next" "build")
    local major_latest=$(Extract-VersionPart "$image_tag_name_latest_related" "major")
    local minor_latest=$(Extract-VersionPart "$image_tag_name_latest_related" "minor")
    local patch_latest=$(Extract-VersionPart "$image_tag_name_latest_related" "patch")
    local build_latest=$(Extract-VersionPart "$image_tag_name_latest_related" "build")

    # Digest Rule Definition Analysis
        if [ "$image_tag_name_current" == "$image_tag_name_next" ]; then
            echo "$rule_digests"
            return
        fi

    # Major Rule Definition Analysis
        if [[ "$major_current" != "$major_next" ]]; then
            if [[ "$rule_major" =~ ^[0-9]+$ ]]; then
                # If the rule for major updates is solely numeric, we can assume that there is no more precise rule definition that
                if ((major_latest - major_current >= rule_major)) && [ "$rule_major" -gt 0 ]; then
                    echo true
                    return
                fi
            else
                # If the value is not exclusively numeric, we need to conduct a more precise rule definition analysis
                rule_major_main=$(echo "$rule_major" | $cmd_awk -F '&\\(' '{print $1}') # e.g. 2
                rule_set_major=$(echo "$rule_major" | $cmd_awk -F '&\\(' '{print $2}' | $cmd_sed 's/)$//') # e.g. Currently supported values for more precised rules are single ones, like: "M>0", "m>0", "p>0" or "b>0". In a future version combinations like "m>0|p=0&b<2" are planned
                compare_operator="${rule_set_major:1:1}"
                compare_val="$(echo $rule_set_major | $cmd_sed 's/[^0-9]*//g')"
                if ((major_latest - major_current >= rule_major_main)); then
                    if [ $(echo $rule_set_major | $cmd_cut -c 1) == "b" ]; then
                        if [[ $build_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$build_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$build_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$build_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    elif [ $(echo $rule_set_major | $cmd_cut -c 1) == "p" ]; then
                        if [[ $patch_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$patch_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$patch_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$patch_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    elif [ $(echo $rule_set_major | $cmd_cut -c 1) == "m" ]; then
                        if [[ $minor_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$minor_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$minor_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$minor_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    elif [ $(echo $rule_set_major | $cmd_cut -c 1) == "M" ]; then
                        if [[ $major_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$major_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$major_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$major_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    fi
                fi
            fi

            echo false
            return
        fi

    # Minor Rule Definition Analysis
        if [[ "$minor_current" != "$minor_next" ]]; then
            if [[ "$rule_minor" =~ ^[0-9]+$ ]]; then
                # If the rule for minor updates is solely numeric, we can assume that there is no more precise rule definition that
                if ((minor_latest - minor_current >= rule_minor)) && [ "$rule_minor" -gt 0 ]; then
                    echo true
                    return
                fi
            else
                # If the value is not exclusively numeric, we need to conduct a more precise rule definition analysis
                rule_minor_main=$(echo "$rule_minor" | $cmd_awk -F '&\\(' '{print $1}') # e.g. 2
                rule_set_minor=$(echo "$rule_minor" | $cmd_awk -F '&\\(' '{print $2}' | $cmd_sed 's/)$//') # e.g. Currently supported values for more precised rules are single ones, like: "M>0", "m>0", "p>0" or "b>0". In a future version combinations like "m>0|p=0&b<2" are planned
                compare_operator="${rule_set_minor:1:1}"
                compare_val="$(echo $rule_set_minor | $cmd_sed 's/[^0-9]*//g')"
                if ((minor_latest - minor_current >= rule_minor_main)); then
                    if [ $(echo $rule_set_minor | $cmd_cut -c 1) == "b" ]; then
                        if [[ $build_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$build_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$build_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$build_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    elif [ $(echo $rule_set_minor | $cmd_cut -c 1) == "p" ]; then
                        if [[ $patch_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$patch_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$patch_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$patch_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    elif [ $(echo $rule_set_minor | $cmd_cut -c 1) == "m" ]; then
                        if [[ $minor_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$minor_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$minor_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$minor_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    elif [ $(echo $rule_set_minor | $cmd_cut -c 1) == "M" ]; then
                        if [[ $minor_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$minor_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$minor_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$minor_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    fi
                fi
            fi

            echo false
            return
        fi

    # Patch Rule Definition Analysis
        if [[ "$patch_current" != "$patch_next" ]]; then
            if [[ "$rule_patch" =~ ^[0-9]+$ ]]; then
                # If the rule for patch updates is solely numeric, we can assume that there is no more precise rule definition that
                if ((patch_latest - patch_current >= rule_patch)) && [ "$rule_patch" -gt 0 ]; then
                    echo true
                    return
                fi
            else
                # If the value is not exclusively numeric, we need to conduct a more precise rule definition analysis
                rule_patch_main=$(echo "$rule_patch" | $cmd_awk -F '&\\(' '{print $1}') # e.g. 2
                rule_set_patch=$(echo "$rule_patch" | $cmd_awk -F '&\\(' '{print $2}' | $cmd_sed 's/)$//') # e.g. Currently supported values for more precised rules are single ones, like: "M>0", "m>0", "p>0" or "b>0". In a future version combinations like "m>0|p=0&b<2" are planned
                compare_operator="${rule_set_patch:1:1}"
                compare_val="$(echo $rule_set_patch | $cmd_sed 's/[^0-9]*//g')"
                if ((patch_latest - patch_current >= rule_patch_main)); then
                    if [ $(echo $rule_set_patch | $cmd_cut -c 1) == "b" ]; then
                        if [[ $build_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$build_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$build_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$build_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    elif [ $(echo $rule_set_patch | $cmd_cut -c 1) == "p" ]; then
                        if [[ $patch_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$patch_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$patch_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$patch_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    elif [ $(echo $rule_set_patch | $cmd_cut -c 1) == "m" ]; then
                        if [[ $patch_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$patch_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$patch_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$patch_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    elif [ $(echo $rule_set_patch | $cmd_cut -c 1) == "M" ]; then
                        if [[ $patch_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$patch_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$patch_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$patch_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    fi
                fi
            fi

            echo false
            return
        fi

    # Build Rule Definition Analysis
        if [[ "$build_current" != "$build_next" ]]; then
            if [[ "$rule_build" =~ ^[0-9]+$ ]]; then
                # If the rule for build updates is solely numeric, we can assume that there is no more precise rule definition that
                if ((build_latest - build_current >= rule_build)) && [ "$rule_build" -gt 0 ]; then
                    echo true
                    return
                fi
            else
                # If the value is not exclusively numeric, we need to conduct a more precise rule definition analysis
                rule_build_main=$(echo "$rule_build" | $cmd_awk -F '&\\(' '{print $1}') # e.g. 2
                rule_set_build=$(echo "$rule_build" | $cmd_awk -F '&\\(' '{print $2}' | $cmd_sed 's/)$//') # e.g. Currently supported values for more precised rules are single ones, like: "M>0", "m>0", "p>0" or "b>0". In a future version combinations like "m>0|p=0&b<2" are planned
                compare_operator="${rule_set_build:1:1}"
                compare_val="$(echo $rule_set_build | $cmd_sed 's/[^0-9]*//g')"
                if ((build_latest - build_current >= rule_build_main)); then
                    if [ $(echo $rule_set_build | $cmd_cut -c 1) == "b" ]; then
                        if [[ $build_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$build_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$build_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$build_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    elif [ $(echo $rule_set_build | $cmd_cut -c 1) == "p" ]; then
                        if [[ $build_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$build_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$build_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$build_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    elif [ $(echo $rule_set_build | $cmd_cut -c 1) == "m" ]; then
                        if [[ $build_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$build_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$build_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$build_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    elif [ $(echo $rule_set_build | $cmd_cut -c 1) == "M" ]; then
                        if [[ $build_latest =~ ^[0-9]+$ ]] && [[ $compare_val =~ ^[0-9]+$ ]]; then
                            case $compare_operator in
                                ">") if [ "$build_latest" -gt "$compare_val" ]; then echo true && return; fi ;;
                                "<") if [ "$build_latest" -lt "$compare_val" ]; then echo true && return; fi ;;
                                "=") if [ "$build_latest" -eq "$compare_val" ]; then echo true && return; fi ;;
                                *) echo "Invalid comparison operator passed";;
                            esac
                        fi
                    fi
                fi
            fi

            echo false
            return
        fi

    echo false
    return
}

Get-ImageURL() {
    local image_name="$1"
    local docker_hub_api_url=$(Read-INI "$configFile" "general" "docker_hub_api_url")
    local ghcr_api_url=$(Read-INI "$configFile" "general" "github_container_registry_api_url")

    if [[ $image_name == 'ghcr.io/'* ]]; then
        image_name="${image_name#ghcr.io/}"
        echo "${ghcr_api_url}/${image_name}"
    elif [[ $image_name == *'/'* ]]; then
        echo "$docker_hub_api_url/repositories/${image_name}"
        return
    else
        echo "$docker_hub_api_url/repositories/library/${image_name}"
        return
    fi
}

Get-DockerHubImageTags() {
    local image_name=$1
    local docker_hub_api_image_tags_page_size_limit=$(Read-INI "$configFile" "general" "docker_hub_api_image_tags_page_size_limit")
    local docker_hub_api_image_tags_page_crawl_limit=$(Read-INI "$configFile" "general" "docker_hub_api_image_tags_page_crawl_limit")
    local github_container_repository_api_image_tags_page_size_limit=$(Read-INI "$configFile" "general" "github_container_repository_api_image_tags_page_size_limit")
    local github_container_repository_api_image_tags_page_crawl_limit=$(Read-INI "$configFile" "general" "github_container_repository_api_image_tags_page_crawl_limit")
    local cmd_awk=$(Read-INI "$configFile" "paths" "gawk")
    local cmd_curl=$(Read-INI "$configFile" "paths" "curl")
    local cmd_grep=$(Read-INI "$configFile" "paths" "grep")
    local cmd_jq=$(Read-INI "$configFile" "paths" "jq")
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed")
    local cmd_wget=$(Read-INI "$configFile" "paths" "wget")
    local url=""
    local image_tags=""
    local image_tags_file="$(mktemp)"

    trap "rm -f $image_tags_file" EXIT

    if [[ $image_name == 'ghcr.io/'* ]]; then
        local page=0
        local auth_token=$($cmd_curl -s "https://ghcr.io/token?scope=repository:${image_name}:pull" | $cmd_awk -F'"' '$0=$4')
        local image_tags_url="https://ghcr.io/v2/${image_name}/tags/list?n=$github_container_repository_api_image_tags_page_size_limit"

        while [[ -n "$image_tags_url" ]] && (( page < github_container_repository_api_image_tags_page_crawl_limit )); do
            page=$((page + 1))
            response=$($cmd_curl -s -D - --insecure -H "Authorization: Bearer $auth_token" "$image_tags_url")
            docker_image_tags+=$(echo "$response" | $cmd_awk '/^\{/ {json=1} json {print}' | $cmd_jq -r '.tags[]'; printf '\n')
            image_tags_url=$(echo "$response" | $cmd_grep -oi 'link:.*rel="next"' | $cmd_sed -n 's/.*<\(.*\)>.*$/\1/p')

            if [[ -n "$image_tags_url" ]]; then
                image_tags_url="https://ghcr.io${image_tags_url}"
            fi
        done

        # Prepare entries in $image_tags_file
        echo '{"count": 0, "next": null, "previous": null, "results": [' >> "$image_tags_file"

        # Convert docker_image_tags into an array to optimize the loop
        docker_image_tags_array=($docker_image_tags)
        total_tags=${#docker_image_tags_array[@]}

        # Iterate through tags and check if it is the last element
        for ((i = 0; i < total_tags; i++)); do
            docker_image_tag="${docker_image_tags_array[i]}"

            # Start the JSON structure for each image tag
            echo '{"images": [' >> "$image_tags_file"
            echo "], \"name\": \"${docker_image_tag}\" }" >> "$image_tags_file"

            # Add a comma only if this is not the last element
            if (( i < total_tags - 1 )); then
                echo "," >> "$image_tags_file"
            fi
        done

        # Complete the JSON structure
        echo ']}' >> "$image_tags_file"
    else
        for ((page=1; page<=$docker_hub_api_image_tags_page_crawl_limit; page++)); do
            url="$(Get-ImageURL "$image_name")/tags?page_size=${docker_hub_api_image_tags_page_size_limit}&page=${page}"
            response=$($cmd_wget -q --no-check-certificate "$url" -O - 2>&1 )
            if [[ -z $response ]]; then
                break
            else
                echo "$response" >> "$image_tags_file"
            fi
        done
    fi

    tr -d '\n' < "$image_tags_file"
    return
}

Get-DockerHubImageTagNames() {
    local jsondata=$1
    local returnType=$2
    local imageTagNameFilter=$3
    local currentContainerImageTag=$4
    local cmd_jq=$(Read-INI "$configFile" "paths" "jq")
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed")
    local cmd_grep=$(Read-INI "$configFile" "paths" "grep")
    local cmd_sort=$(Read-INI "$configFile" "paths" "sort")
    local cmd_awk=$(Read-INI "$configFile" "paths" "gawk")

    if ! $cmd_jq -e . >/dev/null 2>&1 <<<"$jsondata"; then
        Write-Log "ERROR" "Invalid json data passed to \"Get-DockerHubImageTagNames()\""
        return
    fi

    if   [ -z "$returnType" ]; then
        echo $(echo "$jsondata" | $cmd_jq -r '.results[].name' | $cmd_sed 's/^ *//')
        return
    fi
}

Get-DockerHubImageTagProperty() {
    local jsondata=$1
    local imageTagName=$2
    local property=$3
    local cmd_cut=$(Read-INI "$configFile" "paths" "cut")
    local cmd_jq=$(Read-INI "$configFile" "paths" "jq")
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed")

    if ! $cmd_jq -e . >/dev/null 2>&1 <<<"$jsondata"; then
        Write-Log "ERROR" "Invalid json data passed to \"Get-DockerHubImageTagProperty()\""
        return
    fi

    if   [ "$property" == "docker_hub_image_tag_digest" ]; then
        #echo $(echo "$jsondata" | $cmd_jq -r --arg name "$imageTagName" '.results[] | select(.name == $name) | .images[].digest' | $cmd_sed 's/^null$//') # gets all digests for all architectures
        echo $(echo "$jsondata" | $cmd_jq -r --arg name "$imageTagName" '.results[] | select(.name == $name) | .digest' | $cmd_cut -d':' -f2 | $cmd_sed 's/^null$//')
        return
    elif [ "$property" == "docker_hub_image_tag_last_updated" ]; then
        echo $(echo "$jsondata" | $cmd_jq -r --arg name "$imageTagName" '.results[] | select(.name == $name) | .last_updated' | $cmd_sed 's/^null$//')
        return
    else
        Write-Log "ERROR" "Unknown property requested: $property"
    fi
}

Get-AvailableUpdates() {
    local updateType=$1
    local cmd_awk=$(Read-INI "$configFile" "paths" "gawk")
    local cmd_grep=$(Read-INI "$configFile" "paths" "grep")
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed")
    local cmd_sort=$(Read-INI "$configFile" "paths" "sort")

    if   [ "$updateType" == "all" ]; then
        local docker_hub_image_tag_names=$2
        local filter=$3
        local container_image_tag=$4

        echo $(echo "$docker_hub_image_tag_names" | tr ' ' '\n' | $cmd_grep -E "$filter" | tr ' ' '\n' | $cmd_sort -rV | $cmd_awk -v pattern="$container_image_tag" '$0 ~ ("^" pattern "$"){p=1} !p' | tr '\n' ' ')
        return
    fi

    if   [ "$updateType" == "major" ]; then
        local docker_hub_image_tag_names=$(echo $2 | tr ' ' '\n')
        local container_image_tag=$3
        local return_request=$4
        local major_version_current=$(Extract-VersionPart $container_image_tag "major")

        for tag in $docker_hub_image_tag_names; do
            major_version_online=$(Extract-VersionPart $tag "major")
            if [ "$return_request" == "next" ]; then
                if [ "$major_version_online" -le "$major_version_current" ]; then
                    break
                else
                    return_value=$tag
                fi
            elif [ "$return_request" == "latest" ]; then
                return_value=$tag
                break
            fi
        done

        echo $return_value
        return
    fi

    if   [ "$updateType" == "minor" ]; then
        local docker_hub_image_tag_names=$(echo $2 | tr ' ' '\n')
        local container_image_tag=$3
        local return_request=$4
        local major_version_current=$(Extract-VersionPart $container_image_tag "major")
        local minor_version_current=$(Extract-VersionPart $container_image_tag "minor")

        for tag in $docker_hub_image_tag_names; do
            major_version_online=$(Extract-VersionPart $tag "major")
            minor_version_online=$(Extract-VersionPart $tag "minor")
            if [ "$return_request" == "next" ]; then
                if [ "$major_version_online" -eq "$major_version_current" ] && [ "$minor_version_online" -le "$minor_version_current" ]; then
                    break
                else
                    if [ "$major_version_online" -eq "$major_version_current" ]; then
                        return_value=$tag
                    else
                        return_value=""
                    fi
                fi
            elif [ "$return_request" == "latest" ]; then
                if [ "$major_version_online" -eq "$major_version_current" ]; then
                    return_value=$tag
                    break
                else
                    return_value=""
                fi
            fi
        done

        echo $return_value
        return
    fi

    if   [ "$updateType" == "patch" ]; then
        local docker_hub_image_tag_names=$(echo $2 | tr ' ' '\n')
        local container_image_tag=$3
        local return_request=$4
        local major_version_current=$(Extract-VersionPart $container_image_tag "major")
        local minor_version_current=$(Extract-VersionPart $container_image_tag "minor")
        local patch_version_current=$(Extract-VersionPart $container_image_tag "patch")

        for tag in $docker_hub_image_tag_names; do
            major_version_online=$(Extract-VersionPart $tag "major")
            minor_version_online=$(Extract-VersionPart $tag "minor")
            patch_version_online=$(Extract-VersionPart $tag "patch")
            if [ "$return_request" == "next" ]; then
                if [ "$major_version_online" -eq "$major_version_current" ] && [ "$minor_version_online" -eq "$minor_version_current" ] && [ "$patch_version_online" -le "$patch_version_current" ]; then
                    break
                else
                    if [ "$major_version_online" -eq "$major_version_current" ] && [ "$minor_version_online" -eq "$minor_version_current" ]; then
                        return_value=$tag
                    else
                        return_value=""
                    fi
                fi
            elif [ "$return_request" == "latest" ]; then
                if [ "$major_version_online" -eq "$major_version_current" ] && [ "$minor_version_online" -eq "$minor_version_current" ]; then
                    return_value=$tag
                    break
                else
                    return_value=""
                fi
            fi
        done

        echo $return_value
        return
    fi

    if   [ "$updateType" == "build" ]; then
        local docker_hub_image_tag_names=$(echo $2 | tr ' ' '\n')
        local container_image_tag=$3
        local return_request=$4
        local major_version_current=$(Extract-VersionPart $container_image_tag "major")
        local minor_version_current=$(Extract-VersionPart $container_image_tag "minor")
        local patch_version_current=$(Extract-VersionPart $container_image_tag "patch")
        local build_version_current=$(Extract-VersionPart $container_image_tag "build")

        for tag in $docker_hub_image_tag_names; do
            major_version_online=$(Extract-VersionPart $tag "major")
            minor_version_online=$(Extract-VersionPart $tag "minor")
            patch_version_online=$(Extract-VersionPart $tag "patch")
            build_version_online=$(Extract-VersionPart $tag "build")
            if [ "$return_request" == "next" ]; then
                if [ "$major_version_online" -eq "$major_version_current" ] && [ "$minor_version_online" -eq "$minor_version_current" ] && [ "$patch_version_online" -eq "$patch_version_current" ] && [ "$build_version_online" -le "$build_version_current" ]; then
                    break
                else
                    if [ "$major_version_online" -eq "$major_version_current" ] && [ "$minor_version_online" -eq "$minor_version_current" ] && [ "$patch_version_online" -eq "$patch_version_current" ]; then
                        return_value=$tag
                    else
                        return_value=""
                    fi
                fi
            elif [ "$return_request" == "latest" ]; then
                if [ "$major_version_online" -eq "$major_version_current" ] && [ "$minor_version_online" -eq "$minor_version_current" ] && [ "$patch_version_online" -eq "$patch_version_current" ]; then
                    return_value=$tag
                    break
                else
                    return_value=""
                fi
            fi
        done

        echo $return_value
        return
    fi

    if   [ "$updateType" == "digest" ]; then
        local image_repoDigests=$2
        local docker_hub_image_tag_digest=$3

        if [ -n "$image_repoDigests" ] && [ -n "$docker_hub_image_tag_digest" ]; then

            for digest in $image_repoDigests; do
                if echo "$docker_hub_image_tag_digest" | $cmd_grep -q "\<$digest\>"; then
                    echo false
                    return
                fi
            done

            for digest in $docker_hub_image_tag_digest; do
                if echo "$image_repoDigests" | $cmd_grep -q "\<$digest\>"; then
                    echo false
                    return
                fi
            done

            echo true
            return
        else
            echo false
            Write-Log "WARNING" "                => An empty value was passed to \"Get-AvailableUpdates()\" - Either the Image Repository Digests, or the Docker Hub Image Digest was not found"
            return
        fi
    fi
}

Perform-ImageUpdate() {
    local update_type="$1"
    local container_name="$2"
    local container_state_paused="$3"
    local container_restartPolicy_name="$4"
    local image_name="$5"
    local docker_run_cmd="$6"
    local image_tag_old="$7"
    local image_tag_new="$8"
    local test_mode="$test_mode"
    local cmd_docker=$(Read-INI "$configFile" "paths" "docker")
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed")
    local cmd_grep=$(Read-INI "$configFile" "paths" "grep")
    local image_pulled_successfully=false
    local container_renamed_successfully=false
    local new_container_started_successfully=false
    local old_container_stopped_successfully=false
    local datetime=$(date +%Y-%m-%d_%H-%M)
    local container_update_validation_time=$(Read-INI "$configFile" "general" "container_update_validation_time")
    local container_update_pre_scripts_folder=$(Read-INI "$configFile" "general" "pre_scripts_folder")
    local container_update_post_scripts_folder=$(Read-INI "$configFile" "general" "post_scripts_folder")
    local container_update_pre_script="$container_update_pre_scripts_folder/$container_name.sh"
    local container_update_post_script="$container_update_post_scripts_folder/$container_name.sh"
    local container_name_backed_up="${container_name}_bak_$(date +%Y-%m-%d_%H-%M)"
    local result=0
    local this_errors_count=0
    [ "$update_type" == "digest" ] && image_tag_new="$image_tag_old"

    if [ -n "$container_update_pre_scripts_folder" ] && [ -n "$container_update_pre_script" ]; then
        mkdir -p "$container_update_pre_scripts_folder" 2>/dev/null
        touch "$container_update_pre_script" 2>/dev/null
        chmod +w "$container_update_pre_script" 2>/dev/null
        chmod +x "$container_update_pre_script" 2>/dev/null
    fi

    if [ -n "$container_update_post_scripts_folder" ] && [ -n "$container_update_post_script" ]; then
        mkdir -p "$container_update_post_scripts_folder" 2>/dev/null
        touch "$container_update_post_script" 2>/dev/null
        chmod +w "$container_update_post_script" 2>/dev/null
        chmod +x "$container_update_post_script" 2>/dev/null
    fi

    Write-Log "INFO"  "    <print_line_top>"
    Write-Log "INFO"  "    ║ UPDATE PROGRESS"
    Write-Log "INFO"  "    <print_line_btn>"

    [ "$test_mode" == false ] && [ "$update_type" == "digest" ] && Write-Log "INFO" "       Performing a $update_type update for $container_name ($image_name:$image_tag_old)..."
    [ "$test_mode" == true  ] && [ "$update_type" == "digest" ] && Write-Log "INFO" "       Simulating a $update_type update for $container_name ($image_name:$image_tag_old)..."
    [ "$test_mode" == false ] && [ "$update_type" != "digest" ] && Write-Log "INFO" "       Performing a $update_type update for $container_name ($image_name:$image_tag_old to $image_name:$image_tag_new)..."
    [ "$test_mode" == true  ] && [ "$update_type" != "digest" ] && Write-Log "INFO" "       Simulating a $update_type update for $container_name ($image_name:$image_tag_old to $image_name:$image_tag_new)..."

    # Pull new image
    [ "$test_mode" == false ] && Write-Log "INFO"  "           Pulling new image from Docker Hub $image_name:$image_tag_new..."
    [ "$test_mode" == true  ] && Write-Log "INFO"  "           Simulating image pull from Docker Hub for $image_name:$image_tag_new..."
    [ "$test_mode" == false ] && { $cmd_docker pull $image_name:$image_tag_new > /dev/null; result=$?; } || result=$?
    [ "$test_mode" == false ] && [ $result -eq 0 ] && image_pulled_successfully=true  && Write-Log "DEBUG" "             => Image successfully pulled"
    [ "$test_mode" == false ] && [ $result -ne 0 ] && image_pulled_successfully=false && Write-Log "ERROR" "             => Failed to pull image: $result"

    if  [ "$image_name" == "janjk/docker-container-updater" ] && \
        [ "$container_name" != "${container_name}_DCU_SelfUpdateHelper" ] && \
        ! docker ps -a --format '{{.Names}}' | grep -Eq "^${container_name}_DCU_SelfUpdateHelper\$"; then

        # Run self-update helper container
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true  ] && Write-Log "INFO"  "           Bringing up self-update helper container..."
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true  ] && Write-Log "DEBUG" "             => $cmd_docker run -d --rm --name="$container_name"_DCU_SelfUpdateHelper --privileged --tty --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock --env DCU_TEST_MODE=false --env DCU_UPDATE_RULES='*[0.0.0-0,false] $container_name[1.1.1-1,true]' --env DCU_MAIL_NOTIFICATIONS_ENABLED=\"$DCU_MAIL_NOTIFICATIONS_ENABLED\" --env DCU_MAIL_NOTIFICATION_MODE=\"$DCU_MAIL_NOTIFICATION_MODE\" --env DCU_MAIL_FROM=\"$DCU_MAIL_FROM\" --env DCU_MAIL_RECIPIENTS=\"$DCU_MAIL_RECIPIENTS\" --env DCU_MAIL_SUBJECT=\"$DCU_MAIL_SUBJECT\" --env DCU_MAIL_RELAYHOST=\"$DCU_MAIL_RELAYHOST\" --env DCU_TELEGRAM_NOTIFICATIONS_ENABLED=\"$DCU_TELEGRAM_NOTIFICATIONS_ENABLED\" --env DCU_TELEGRAM_RETRY_LIMIT=\"$DCU_TELEGRAM_RETRY_LIMIT\" --env DCU_TELEGRAM_RETRY_INTERVAL=\"$DCU_TELEGRAM_RETRY_INTERVAL\" --env DCU_TELEGRAM_CHAT_ID=\"$DCU_TELEGRAM_CHAT_ID\" --env DCU_TELEGRAM_BOT_TOKEN=\"$DCU_TELEGRAM_BOT_TOKEN\" --env DCU_REPORT_REAL_HOSTNAME=\"$DCU_REPORT_REAL_HOSTNAME\" --env DCU_REPORT_REAL_IP=\"$DCU_REPORT_REAL_IP\" --env DCU_REPORT_REAL_DOCKER_VERSION=\"$DCU_REPORT_REAL_DOCKER_VERSION\" --env DCU_DOCKER_HUB_API_URL=\"$DCU_DOCKER_HUB_API_URL\" --env DCU_GITHUB_CONTAINER_REPOSITORY_API_URL=\"$DCU_GITHUB_CONTAINER_REPOSITORY_API_URL\" --env DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_SIZE_LIMIT=\"$DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_SIZE_LIMIT\" --env DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_CRAWL_LIMIT=\"$DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_CRAWL_LIMIT\" --env DCU_DOCKER_HUB_IMAGE_MINIMUM_AGE=\"$DCU_DOCKER_HUB_IMAGE_MINIMUM_AGE\" --env DCU_CONTAINER_UPDATE_VALIDATION_TIME=\"$DCU_CONTAINER_UPDATE_VALIDATION_TIME\" --env DCU_LOG_LEVEL=\"DEBUG\" $image_name:$image_tag_new dcu --self-update --filter name=$container_name"
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true  ] && { $cmd_docker run -d --rm --name="${container_name}_DCU_SelfUpdateHelper" --privileged --tty --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock --env DCU_TEST_MODE=false --env DCU_UPDATE_RULES='*[0.0.0-0,false] '$container_name'[1.1.1-1,true]' --env DCU_MAIL_NOTIFICATIONS_ENABLED="$DCU_MAIL_NOTIFICATIONS_ENABLED" --env DCU_MAIL_NOTIFICATION_MODE="$DCU_MAIL_NOTIFICATION_MODE" --env DCU_MAIL_FROM="$DCU_MAIL_FROM" --env DCU_MAIL_RECIPIENTS="$DCU_MAIL_RECIPIENTS" --env DCU_MAIL_SUBJECT="$DCU_MAIL_SUBJECT" --env DCU_MAIL_RELAYHOST="$DCU_MAIL_RELAYHOST" --env DCU_TELEGRAM_NOTIFICATIONS_ENABLED="$DCU_TELEGRAM_NOTIFICATIONS_ENABLED" --env DCU_TELEGRAM_RETRY_LIMIT="$DCU_TELEGRAM_RETRY_LIMIT" --env DCU_TELEGRAM_RETRY_INTERVAL="$DCU_TELEGRAM_RETRY_INTERVAL" --env DCU_TELEGRAM_CHAT_ID="$DCU_TELEGRAM_CHAT_ID" --env DCU_TELEGRAM_BOT_TOKEN="$DCU_TELEGRAM_BOT_TOKEN" --env DCU_REPORT_REAL_HOSTNAME="$DCU_REPORT_REAL_HOSTNAME" --env DCU_REPORT_REAL_IP="$DCU_REPORT_REAL_IP" --env DCU_REPORT_REAL_DOCKER_VERSION="$DCU_REPORT_REAL_DOCKER_VERSION" --env DCU_DOCKER_HUB_API_URL="$DCU_DOCKER_HUB_API_URL" --env DCU_GITHUB_CONTAINER_REPOSITORY_API_URL="$DCU_GITHUB_CONTAINER_REPOSITORY_API_URL" --env DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_SIZE_LIMIT="$DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_SIZE_LIMIT" --env DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_CRAWL_LIMIT="$DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_CRAWL_LIMIT" --env DCU_DOCKER_HUB_IMAGE_MINIMUM_AGE="$DCU_DOCKER_HUB_IMAGE_MINIMUM_AGE" --env DCU_CONTAINER_UPDATE_VALIDATION_TIME="$DCU_CONTAINER_UPDATE_VALIDATION_TIME" --env DCU_LOG_LEVEL="DEBUG" $image_name:$image_tag_new dcu --self-update --filter name=$container_name > /dev/null; result=$?; } || result=$?
        # [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true  ] && Write-Log "DEBUG" "             => $cmd_docker run -d --rm --name="$container_name"_DCU_SelfUpdateHelper --privileged --tty --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock --env DCU_TEST_MODE=false --env DCU_UPDATE_RULES='*[0.0.0-0,false] $container_name[1.1.1-1,true]' --env DCU_MAIL_NOTIFICATIONS_ENABLED=\"$DCU_MAIL_NOTIFICATIONS_ENABLED\" --env DCU_MAIL_NOTIFICATION_MODE=\"$DCU_MAIL_NOTIFICATION_MODE\" --env DCU_MAIL_FROM=\"$DCU_MAIL_FROM\" --env DCU_MAIL_RECIPIENTS=\"$DCU_MAIL_RECIPIENTS\" --env DCU_MAIL_SUBJECT=\"$DCU_MAIL_SUBJECT\" --env DCU_MAIL_RELAYHOST=\"$DCU_MAIL_RELAYHOST\" --env DCU_TELEGRAM_NOTIFICATIONS_ENABLED=\"$DCU_TELEGRAM_NOTIFICATIONS_ENABLED\" --env DCU_TELEGRAM_RETRY_LIMIT=\"$DCU_TELEGRAM_RETRY_LIMIT\" --env DCU_TELEGRAM_RETRY_INTERVAL=\"$DCU_TELEGRAM_RETRY_INTERVAL\" --env DCU_TELEGRAM_CHAT_ID=\"$DCU_TELEGRAM_CHAT_ID\" --env DCU_TELEGRAM_BOT_TOKEN=\"$DCU_TELEGRAM_BOT_TOKEN\" --env DCU_REPORT_REAL_HOSTNAME=\"$DCU_REPORT_REAL_HOSTNAME\" --env DCU_REPORT_REAL_IP=\"$DCU_REPORT_REAL_IP\" --env DCU_REPORT_REAL_DOCKER_VERSION=\"$DCU_REPORT_REAL_DOCKER_VERSION\" --env DCU_DOCKER_HUB_API_URL=\"$DCU_DOCKER_HUB_API_URL\" --env DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_SIZE_LIMIT=\"$DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_SIZE_LIMIT\" --env DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_CRAWL_LIMIT=\"$DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_CRAWL_LIMIT\" --env DCU_DOCKER_HUB_IMAGE_MINIMUM_AGE=\"$DCU_DOCKER_HUB_IMAGE_MINIMUM_AGE\" --env DCU_CONTAINER_UPDATE_VALIDATION_TIME=\"$DCU_CONTAINER_UPDATE_VALIDATION_TIME\" --env DCU_LOG_LEVEL=\"DEBUG\" $image_name:$image_tag_new dcu --self-update --filter name=$container_name"
        # [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true  ] && { $cmd_docker run -d --rm --name="${container_name}_DCU_SelfUpdateHelper" --privileged --tty --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock --env DCU_TEST_MODE=false --env DCU_UPDATE_RULES='*[0.0.0-0,false] '$container_name'[1.1.1-1,true]' --env DCU_MAIL_NOTIFICATIONS_ENABLED="$DCU_MAIL_NOTIFICATIONS_ENABLED" --env DCU_MAIL_NOTIFICATION_MODE="$DCU_MAIL_NOTIFICATION_MODE" --env DCU_MAIL_FROM="$DCU_MAIL_FROM" --env DCU_MAIL_RECIPIENTS="$DCU_MAIL_RECIPIENTS" --env DCU_MAIL_SUBJECT="$DCU_MAIL_SUBJECT" --env DCU_MAIL_RELAYHOST="$DCU_MAIL_RELAYHOST" --env DCU_TELEGRAM_NOTIFICATIONS_ENABLED="$DCU_TELEGRAM_NOTIFICATIONS_ENABLED" --env DCU_TELEGRAM_RETRY_LIMIT="$DCU_TELEGRAM_RETRY_LIMIT" --env DCU_TELEGRAM_RETRY_INTERVAL="$DCU_TELEGRAM_RETRY_INTERVAL" --env DCU_TELEGRAM_CHAT_ID="$DCU_TELEGRAM_CHAT_ID" --env DCU_TELEGRAM_BOT_TOKEN="$DCU_TELEGRAM_BOT_TOKEN" --env DCU_REPORT_REAL_HOSTNAME="$DCU_REPORT_REAL_HOSTNAME" --env DCU_REPORT_REAL_IP="$DCU_REPORT_REAL_IP" --env DCU_REPORT_REAL_DOCKER_VERSION="$DCU_REPORT_REAL_DOCKER_VERSION" --env DCU_DOCKER_HUB_API_URL="$DCU_DOCKER_HUB_API_URL" --env DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_SIZE_LIMIT="$DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_SIZE_LIMIT" --env DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_CRAWL_LIMIT="$DCU_DOCKER_HUB_API_IMAGE_TAGS_PAGE_CRAWL_LIMIT" --env DCU_DOCKER_HUB_IMAGE_MINIMUM_AGE="$DCU_DOCKER_HUB_IMAGE_MINIMUM_AGE" --env DCU_CONTAINER_UPDATE_VALIDATION_TIME="$DCU_CONTAINER_UPDATE_VALIDATION_TIME" --env DCU_LOG_LEVEL="DEBUG" $image_name:$image_tag_new dcu --self-update --filter name=$container_name > /dev/null; result=$?; } || result=$?
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true  ] && [ $result -eq 0 ] && new_container_started_successfully=true  && Write-Log "DEBUG" "             => Self-update helper container started successfully"
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true  ] && [ $result -ne 0 ] && new_container_started_successfully=false && Write-Log "ERROR" "             => Failed to start self-update helper container: $result"
        [ "$test_mode" == false ] && [ "$new_container_started_successfully" == true  ] && self_update_helper_container_started=true && self_update_helper_container_name="${container_name}_DCU_SelfUpdateHelper"

    else
        # Execute pre script
        if [ -s "$container_update_pre_script" ] && [ "$image_pulled_successfully" == true ]; then
            [ "$test_mode" == false ] && Write-Log "INFO" "           Executing pre script $container_update_pre_script..."
            [ "$test_mode" == true ]  && Write-Log "INFO" "           Would execute pre script $container_update_pre_script..."
                if [ "$test_mode" == false ]; then
                    chmod +x "$container_update_pre_script" 2>/dev/null
                    while IFS= read -r line; do
                        Write-Log "INFO" "           | $container_update_pre_script: $line"
                    done < <("$container_update_pre_script")
                fi
        fi

        # Rename old container
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true ] && Write-Log "INFO"  "           Renaming current docker container from $container_name to $container_name_backed_up..."
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true ] && { $cmd_docker rename "$container_name" "$container_name_backed_up" > /dev/null; result=$?; } || result=$?
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true ] && [ $result -eq 0 ] && container_renamed_successfully=true  && Write-Log "DEBUG" "             => Container successfully renamed"
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true ] && [ $result -ne 0 ] && container_renamed_successfully=false && Write-Log "ERROR" "             => Failed to rename container: $result"

        # Disable old containers start up policy
        [ "$test_mode" == false ] && [ "$container_renamed_successfully" == true  ] && Write-Log "INFO"  "           Disabling automatic startup for $container_name_backed_up..."
        [ "$test_mode" == false ] && [ "$container_renamed_successfully" == true  ] && { $cmd_docker update "$container_name_backed_up" --restart no > /dev/null; result=$?; } || result=$?
        [ "$test_mode" == false ] && [ "$container_renamed_successfully" == true  ] && [ $result -eq 0 ] && Write-Log "DEBUG" "             => Successfully updated startup policy"
        [ "$test_mode" == false ] && [ "$container_renamed_successfully" == true  ] && [ $result -ne 0 ] && Write-Log "ERROR" "             => Failed to update startup policy: $result"

        # Stop old container
        [ "$test_mode" == false ] && [ "$container_renamed_successfully" == true  ] && Write-Log "INFO"  "           Stopping $container_name_backed_up..."
        [ "$test_mode" == false ] && [ "$container_renamed_successfully" == true  ] && { $cmd_docker stop "$container_name_backed_up" > /dev/null; result=$?; } || result=$?
        [ "$test_mode" == false ] && [ "$container_renamed_successfully" == true  ] && [ $result -eq 0 ] && old_container_stopped_successfully=true  && Write-Log "DEBUG" "             => Successfully stopped container"
        [ "$test_mode" == false ] && [ "$container_renamed_successfully" == true  ] && [ $result -ne 0 ] && old_container_stopped_successfully=false && Write-Log "ERROR" "             => Failed stop old container: $result"

        # Run new container
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true  ] && [ "$container_renamed_successfully" == true  ] && [ "$old_container_stopped_successfully" == true  ] && Write-Log "INFO"  "           Executing docker run command..."
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true  ] && [ "$container_renamed_successfully" == true  ] && [ "$old_container_stopped_successfully" == true  ] && Write-Log "DEBUG" "             => $docker_run_cmd"
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true  ] && [ "$container_renamed_successfully" == true  ] && [ "$old_container_stopped_successfully" == true  ] && { eval "$docker_run_cmd" > /dev/null; result=$?; } || result=$?
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true  ] && [ "$container_renamed_successfully" == true  ] && [ "$old_container_stopped_successfully" == true  ] && [ $result -eq 0 ] && new_container_started_successfully=true  && Write-Log "DEBUG" "             => New container started successfully"
        [ "$test_mode" == false ] && [ "$image_pulled_successfully" == true  ] && [ "$container_renamed_successfully" == true  ] && [ "$old_container_stopped_successfully" == true  ] && [ $result -ne 0 ] && new_container_started_successfully=false && Write-Log "ERROR" "             => Failed to start new container: $result"
        [ "$test_mode" == true  ] && Write-Log "INFO"  "           Docker command that would be executed: $docker_run_cmd"

        # Validate the state of the new container
        [ "$test_mode" == false ] && [ "$new_container_started_successfully" == true  ] && Write-Log "INFO"  "           Waiting for the duration of $container_update_validation_time seconds to validate the state of $container_name..."
        [ "$test_mode" == false ] && [ "$new_container_started_successfully" == true  ] && sleep $((container_update_validation_time + 2))

        if [ "$test_mode" == false ] && [ "$new_container_started_successfully" == true  ]; then
            Write-Log "INFO" "           Validating state and uptime of $container_name..."
            if $cmd_docker ps --format "{{.Names}}" | $cmd_grep -wq "$container_name"; then
                local container_start_time=$(echo $($cmd_docker inspect --format '{{.State.StartedAt}}' $container_name) | $cmd_sed 's/T/ /;s/\..*Z//')
                local container_start_seconds=$(date -d "$container_start_time" +%s)
                local current_time=$(date -u "+%Y-%m-%d %H:%M:%S")
                local current_time_seconds=$(date -d "$current_time" +%s)
                local elapsed_time=$((current_time_seconds - container_start_seconds))
                if [ "$elapsed_time" -gt "$container_update_validation_time" ]; then
                    Write-Log "DEBUG" "             => The container $container_name has been started since $elapsed_time seconds - This assumes everything worked well during the update process"
                    new_container_started_successfully=true
                else
                    Write-Log "ERROR" "             => The container $container_name has been started since just $elapsed_time seconds - This assumes something went wrong during the update process"
                    new_container_started_successfully=false
                fi
            else
                Write-Log "ERROR" "             => The container $container_name does not exist or is not started at the moment - This assumes something went wrong during the update process"
                new_container_started_successfully=false
            fi
        fi

        # Execute post script
        if [ -s "$container_update_post_script" ] && [ "$new_container_started_successfully" == true ]; then
            [ "$test_mode" == false ] && Write-Log "INFO" "           Executing post script $container_update_post_script..."
            [ "$test_mode" == true ]  && Write-Log "INFO" "           Would execute post script $container_update_post_script..."
                if [ "$test_mode" == false ]; then
                    chmod +x "$container_update_post_script" 2>/dev/null
                    while IFS= read -r line; do
                        Write-Log "INFO" "           | $container_update_post_script: $line"
                    done < <("$container_update_post_script")
                fi
        fi

        # Pause new container if the old container also was in paused state
        [ "$test_mode" == false ] && [ "$new_container_started_successfully" == true ] && [ "$container_state_paused" == true ] && Write-Log "INFO" "           Pausing $container_name..."
        [ "$test_mode" == false ] && [ "$new_container_started_successfully" == true ] && [ "$container_state_paused" == true ] && { $cmd_docker pause $container_name; result=$?; } || result=$?
        [ "$test_mode" == false ] && [ $result -eq 0 ] && [ "$new_container_started_successfully" == true ] && [ "$container_state_paused" == true ] && Write-Log "DEBUG" "             => Container paused successfully"
        [ "$test_mode" == false ] && [ $result -ne 0 ] && [ "$new_container_started_successfully" == true ] && [ "$container_state_paused" == true ] && Write-Log "ERROR" "             => Failed to pause container: $result"

        # Collect some information for the report
        if [ "$new_container_started_successfully" == true ]; then
            report_available=true
            [ "$test_mode" == false ] && [ "$update_type" == "digest" ] && mail_report_actions_taken+="<li>&#x1F7E2; A $update_type update for $container_name ($image_name:$image_tag_old) has been performed</li>" && telegram_report_actions_taken+="🟢 A $update_type update for $(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_old")\\\\) has been performed\n"
            [ "$test_mode" == false ] && [ "$update_type" != "digest" ] && mail_report_actions_taken+="<li>&#x1F7E2; A $update_type update for $container_name from $image_name:$image_tag_old to $image_name:$image_tag_new has been performed</li>" && telegram_report_actions_taken+="🟢 A $update_type update for $(Telegram-EscapeSpecialChars "$container_name") from $(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_old") to $(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_new") has been performed\n"
            [ "$test_mode" == true ]  && [ "$update_type" == "digest" ] && mail_report_actions_taken+="<li>&#x1F7E2; A $update_type update for $container_name ($image_name:$image_tag_old) would have been performed</li>" && telegram_report_actions_taken+="🟢 A $update_type update for $(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_old")\\\\) would have been performed\n"
            [ "$test_mode" == true ]  && [ "$update_type" != "digest" ] && mail_report_actions_taken+="<li>&#x1F7E2; A $update_type update for $container_name from $image_name:$image_tag_old to $image_name:$image_tag_new would have been performed</li>" && telegram_report_actions_taken+="🟢 A $update_type update for $(Telegram-EscapeSpecialChars "$container_name") from $(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_old") to $(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_new") would have been performed\n"
        else
            report_available=true
            [ "$test_mode" == false ] && [ "$update_type" == "digest" ] && mail_report_actions_taken+="<li>&#x1F534; A $update_type update for $container_name ($image_name:$image_tag_old) has failed <i>(please refer to your logs)</li>" && telegram_report_actions_taken+="🔴 A $update_type update for $(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_old")\\\\) has failed \\\\(please refer to your logs\\\\)\n"
            [ "$test_mode" == false ] && [ "$update_type" != "digest" ] && mail_report_actions_taken+="<li>&#x1F534; A $update_type update for $container_name from $image_name:$image_tag_old to $image_name:$image_tag_new has failed <i>(please refer to your logs)</i></li>" && telegram_report_actions_taken+="🔴 A $update_type update for $(Telegram-EscapeSpecialChars "$container_name") from $(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_old") to $(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_new") has failed \\\\(please refer to your logs\\\\)\n"
            [ "$test_mode" == true ]  && [ "$update_type" == "digest" ] && mail_report_actions_taken+="<li>&#x1F7E2; A $update_type update for $container_name ($image_name:$image_tag_old) would have been performed</li>" && telegram_report_actions_taken+="🟢 A $update_type update for $(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_old")\\\\) would have been performed\n"
            [ "$test_mode" == true ]  && [ "$update_type" != "digest" ] && mail_report_actions_taken+="<li>&#x1F7E2; A $update_type update for $container_name from $image_name:$image_tag_old to $image_name:$image_tag_new would have been performed</li>" && telegram_report_actions_taken+="🟢 A $update_type update for $(Telegram-EscapeSpecialChars "$container_name") from $(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_old") to $(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_new") would have been performed\n"
        fi

        # Roll back changes if update failed
        if [ "$test_mode" == false ] && [ "$new_container_started_successfully" == false ] && [ "$container_renamed_successfully" == true ]; then
            Write-Log "WARNING" "           Rolling back changes..."
            Write-Log "INFO"    "               Stopping new container ($container_name)..."
            { $cmd_docker stop $container_name > /dev/null; result=$?; } || result=$?
            [ $result -eq 0 ] && Write-Log "DEBUG" "                 => Successfully stopped container"
            [ $result -ne 0 ] && Write-Log "ERROR" "                 => Failed to stop container" && ((this_errors_count+=1))
            Write-Log "INFO"    "               Removing new container ($container_name)..."
            { $cmd_docker rm -fv $container_name > /dev/null; result=$?; } || result=$?
            [ $result -eq 0 ] && Write-Log "DEBUG" "                 => Successfully removed container"
            [ $result -ne 0 ] && Write-Log "ERROR" "                 => Failed to remove container" && ((this_errors_count+=1))
            Write-Log "INFO"    "               Restoring start up policy for old container ($container_name_backed_up)..."
            { $cmd_docker update $container_name_backed_up --restart $container_restartPolicy_name > /dev/null; result=$?; } || result=$?
            [ $result -eq 0 ] && Write-Log "DEBUG" "                 => Successfully updated start up policy"
            [ $result -ne 0 ] && Write-Log "ERROR" "                 => Failed to update startup policy" && ((this_errors_count+=1))
            Write-Log "INFO"    "               Renaming old docker container from $container_name_backed_up to $container_name..."
            { $cmd_docker rename $container_name_backed_up $container_name > /dev/null; result=$?; } || result=$?
            [ $result -eq 0 ] && Write-Log "DEBUG" "                 => Successfully to rename container"
            [ $result -ne 0 ] && Write-Log "ERROR" "                 => Failed to rename container" && ((this_errors_count+=1))
            Write-Log "INFO"    "               Starting old container ($container_name)..."
            { $cmd_docker start $container_name > /dev/null; result=$?; } || result=$?
            [ $result -eq 0 ] && Write-Log "DEBUG" "                 => Successfully started container"
            [ $result -ne 0 ] && Write-Log "ERROR" "                 => Failed to start container" && ((this_errors_count+=1))

            if [ "$this_errors_count" -eq 0 ]; then
                mail_report_actions_taken+="<ul><li>&#x1F7E2; The original container $container_name ($image_name:$image_tag_old) has been successfully restored</li></ul>"
                telegram_report_actions_taken+="🟢 The original container $(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_old")\\\\) has been successfully restored\n"
            else
                mail_report_actions_taken+="<ul><li>&#x1F7E1; A partly successful attempt was made to restore the original container $container_name ($image_name:$image_tag_old) <i>(please refer to your logs)</i></li></ul>"
                telegram_report_actions_taken+="🟠 A partly successful attempt was made to restore the original container $(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$image_name"):$(Telegram-EscapeSpecialChars "$image_tag_old")\\\\) \\\\(please refer to your logs\\\\)\n"
            fi
            this_errors_count=0
        fi

        Write-Log "INFO" "       Update processed"
    fi
}

Prune-ContainerBackups() {
    local prune_container_backups=$(Read-INI "$configFile" "general" "prune_container_backups")
    local container_backups_retention=$(Read-INI "$configFile" "general" "container_backups_retention")
    local container_backups_keep_last=$(Read-INI "$configFile" "general" "container_backups_keep_last")
    local cmd_docker=$(Read-INI "$configFile" "paths" "docker")
    local container_name_original=""
    local container_backup_date=""
    local container_backup_count=""

    if [ "$prune_container_backups" == true ]; then
        for container_name in $($cmd_docker ps -a --format "{{.Names}}" | sort); do
            if [[ "$container_name" == *_bak_* && -z "$($cmd_docker ps -q -f name=$container_name)" ]]; then
                Write-Log "DEBUG" "    Processing container \"$container_name\""

                container_name_original=$(echo $container_name | sed 's/_bak_.*//')
                container_backup_date=$(echo $container_name | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')
                container_backup_count=$($cmd_docker ps -a --filter "name=^${container_name_original}_bak_" --filter "status=exited" --format '{{.Names}}' | wc -l)

                Write-Log "DEBUG" "        Container Information"
                Write-Log "DEBUG" "            Original Container Name: $container_name_original"
                Write-Log "DEBUG" "            Backup Date:             $container_backup_date"
                Write-Log "DEBUG" "            Available Backups:       $container_backup_count"

                if [[ "$container_backup_date" != "" && "$container_backup_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ && "$container_backup_count" -gt $container_backups_keep_last ]]; then
                    backup_timestamp=$(date -d "$container_backup_date" +%s)
                    current_timestamp=$(date +%s)
                    days_diff=$(( (current_timestamp - backup_timestamp) / 86400 ))
                    if [ $days_diff -ge $container_backups_retention ]; then
                        Write-Log "INFO" "        Removing backed up container $container_name..."
                        { $cmd_docker rm -fv $container_name > /dev/null; result=$?; } || result=$?
                        [ $result -eq 0 ] && Write-Log "DEBUG" "          => Successfully removed container" && report_available=true && mail_report_removed_container_backups+="<li>$container_name</li>" && telegram_report_removed_container_backups+="$(Telegram-EscapeSpecialChars "$container_name")\n"
                        [ $result -ne 0 ] && Write-Log "ERROR" "          => Failed to remove container: $result"
                    else
                        Write-Log "DEBUG" "        The removal of this container backup is skipped as it is less than $container_backups_retention days old"
                    fi
                else
                    if [[ "$container_backup_date" == "" ]]; then
                        Write-Log "ERROR" "        No backup date found in containers name"
                    elif ! [[ "$container_backup_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
                        Write-Log "ERROR" "        Backup date given in containers name is invalid. ($container_backup_date)"
                    elif ! [[ "$container_backup_count" -gt 1 ]]; then
                        Write-Log "DEBUG" "        Removing this container backup is prohibited due to the policy in your configuration file"
                    fi
                fi
            fi
        done
    fi
}

Prune-DockerImages() {
    local prune_images=$(Read-INI "$configFile" "general" "prune_images")
    local cmd_docker=$(Read-INI "$configFile" "paths" "docker")

    if [ "$prune_images" == true ]; then
        Write-Log "INFO" "    Pruning docker images..."
        { $cmd_docker image prune -af > /dev/null; result=$?; } || result=$?
        [ $result -eq 0 ] && Write-Log "DEBUG" "      => Successfully pruned images"
        [ $result -ne 0 ] && Write-Log "ERROR" "      => Failed to prune images: $result"
    fi
}

Telegram-EscapeSpecialChars() {
    local string="$1"
    local cmd_sed="sed"
    local -a special_chars=('\\' '`' '*' '_' '{' '}' '[' ']' '(' ')' '#' '+' '-' '=' '|' '.' '!')

    for char in "${special_chars[@]}"; do
        string=$(echo "$string" | $cmd_sed "s/[$char]/\\\\\\\\\\\\$char/g")
    done

    echo "$string"
}

Telegram-GetMessageLength() {
    local message="$1"
    local length=0
    local i=0
    local escaped=false

    while [ $i -lt ${#message} ]; do
        local char="${message:$i:1}"

        if [ "$char" == "\\" ]; then
            if [ "$escaped" == "true" ]; then
                escaped=false
            else
                escaped=true
            fi
        elif [ "$char" == $'\n' ]; then
            length=$((length + 1))
        elif [[ "$char" == "*" || "$char" == "_" || "$char" == "~" || "$char" == "|" || "$char" == "\`" ]]; then
            if [ "$escaped" == "true" ]; then
                length=$((length + 1))
            fi
            escaped=false
        else
            length=$((length + 1))
            escaped=false
        fi

        i=$((i + 1))
    done

    echo "$length"
}

Telegram-GenerateMessage() {
    local test_mode=$test_mode
    local cmd_cut=$(Read-INI "$configFile" "paths" "cut")
    local cmd_docker=$(Read-INI "$configFile" "paths" "docker")
    local hostname=$(Telegram-EscapeSpecialChars "$(hostname)")
    local primary_IPaddress=$(Telegram-EscapeSpecialChars  "$(hostname -I 2>/dev/null | $cmd_cut -d' ' -f1)")
    local docker_version=$(Telegram-EscapeSpecialChars "$($cmd_docker --version | $cmd_cut -d ' ' -f3 | tr -d ',')")
    local message=""
    local end_time=$(date +%s)
    stats_execution_time=$((end_time - start_time))

    [ -n "$DCU_REPORT_REAL_HOSTNAME" ]          && hostname="$(Telegram-EscapeSpecialChars "$DCU_REPORT_REAL_HOSTNAME")"
    [ -n "$DCU_REPORT_REAL_IP" ]                && primary_IPaddress="$(Telegram-EscapeSpecialChars "$DCU_REPORT_REAL_IP")"
    [ -n "$DCU_REPORT_REAL_DOCKER_VERSION" ]    && docker_version="$(Telegram-EscapeSpecialChars "$DCU_REPORT_REAL_DOCKER_VERSION")"

    if [ "$report_available" == true ]; then
        message+="🐳 *DOCKER CONTAINER UPDATE REPORT*\n"
        message+="\n"
        [ "$test_mode" == true ] && message+="\`\`\`\n"
        [ "$test_mode" == true ] && message+="TEST MODE ENABLED\n"
        [ "$test_mode" == true ] && message+="\`\`\`\n"
        [ "$test_mode" == true ] && message+="\n"
        message+="📌 __*Info*__\n"
        message+="*Hostname:* $hostname\n"
        message+="*IP\\\\-Address:* $primary_IPaddress\n"
        message+="*Docker Version:* $docker_version\n"
        message+="*Script Version:* $(Telegram-EscapeSpecialChars "$(Get-ScriptVersion)")\n"
        message+="\n"
        [ -n "$telegram_report_actions_taken" ] && message+="📋 __*Actions Taken*__\n"
        [ -n "$telegram_report_actions_taken" ] && message+="$telegram_report_actions_taken"
        [ -n "$telegram_report_actions_taken" ] && message+="\n"
        [ -n "$telegram_report_available_updates" ] && message+="🔧 __*Outstanding Updates*__\n"
        [ -n "$telegram_report_available_updates" ] && message+="$telegram_report_available_updates"
        [ -n "$telegram_report_available_updates" ] && message+="\n"
        [ -n "$telegram_report_removed_container_backups" ] && message+="🗑️ __*Removed Container Backups*__\n"
        [ -n "$telegram_report_removed_container_backups" ] && message+="$telegram_report_removed_container_backups"
        [ -n "$telegram_report_removed_container_backups" ] && message+="\n"
        message+="📈 __*Stats*__\n"
        message+="*Script Execution Time:* $stats_execution_time seconds\n"
        message+="*Number of Warnings:* $stats_warnings_count\n"
        message+="*Number of Errors:* $stats_errors_count\n"
    fi

    echo "$message"
    return
}

Telegram-SplitMessage() {
    local message="$1"
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed")
    local max_length=4096
    local current_length=0
    local message_part=""

    if [ -n "$message" ]; then
        message=$(echo $message | $cmd_sed 's/\\n/\n/g')

        while IFS="\n" read -r line; do
            line_length=$(Telegram-GetMessageLength "$line")
            if (( current_length + line_length + 1 > max_length )); then
                Send-TelegramNotification "$message_part"
                message_part="$line"
                current_length=$line_length
            else
                if [[ -n "$message_part" ]]; then
                    message_part+=$'\\n'
                    current_length=$((current_length + 1))
                fi
                message_part+="$line"
                current_length=$((current_length + line_length))
            fi
        done <<< "$message"

        if [[ -n "$message_part" ]]; then
            Send-TelegramNotification "$message_part"
        fi
    else
        Write-Log "INFO" "    There is nothing to report"
    fi
}

Send-MailNotification() {
    local test_mode=$test_mode
    local logFile=$(Read-INI "$configFile" "log" "filePath")
    local mail_mode=$(Read-INI "$configFile" "mail" "mode")
    local mail_from=$(Read-INI "$configFile" "mail" "from")
    local mail_recipients=$(Read-INI "$configFile" "mail" "recipients")
    local mail_subject=$(Read-INI "$configFile" "mail" "subject")
    local cmd_sendmail=$(Read-INI "$configFile" "paths" "sendmail")
    local cmd_cut=$(Read-INI "$configFile" "paths" "cut")
    local cmd_docker=$(Read-INI "$configFile" "paths" "docker")
    local mail_message=""
    local mail_message_file="$(mktemp)"
    local hostname=$(hostname)
    local primary_IPaddress=$(hostname -I 2>/dev/null | $cmd_cut -d' ' -f1)
    local docker_version=$($cmd_docker --version | $cmd_cut -d ' ' -f3 | tr -d ',')
    local end_time=$(date +%s)
    stats_execution_time=$((end_time - start_time))

    [ -n "$DCU_REPORT_REAL_HOSTNAME" ]          && hostname="$DCU_REPORT_REAL_HOSTNAME"
    [ -n "$DCU_REPORT_REAL_IP" ]                && primary_IPaddress="$DCU_REPORT_REAL_IP"
    [ -n "$DCU_REPORT_REAL_DOCKER_VERSION" ]    && docker_version="$DCU_REPORT_REAL_DOCKER_VERSION"

    if [[ "$report_available" == true && -n "$mail_from" && -n "$mail_recipients" && -n "$mail_subject" ]]; then

        end_time=$(date +%s)
        duration=$((end_time - start_time))

        for mail_recipient in $mail_recipients; do
            Write-Log "INFO" "    Generating mail report for recipient \"$mail_recipient\"..."

            mail_message="From: $mail_from\n"
            mail_message+="To: $mail_recipient\n"
            mail_message+="Subject: $mail_subject\n"
            mail_message+="MIME-Version: 1.0\n"
            mail_message+="Content-Type: text/html; charset=UTF-8\n"
            mail_message+="\n"
            mail_message+="<html>\n"
                mail_message+="<body>\n"
                    mail_message+="<p>Ahoi Captain,</p>\n"
                    mail_message+="<p> </p>\n"
                    mail_message+="<p>this email is to notify you of recent changes and available updates for your Docker containers.</p>\n"
                    mail_message+="<p> </p>\n"
                    mail_message+="<div style=\"border: 2px solid #ccc; padding: 0 15px;\">\n"
                        mail_message+="<table border="0" style=\"font-size: 25px;\">"
                        mail_message+="<tr>"
                            mail_message+="<td style=\"font-size: 50px;\">&#x1F433;</td>"
                            mail_message+="<td style=\"padding: 30px 15px; color: #4b4b4b;\"><strong>Docker Container Update Report</strong></td>"
                        mail_message+="</tr>"
                        mail_message+="</table>"

                        mail_message+="<p style=\"font-size: 14px; padding: 0px 5px; color: #4b4b4b;\"><strong>&#x1F4CC; INFO</strong></p>\n"
                        if [ "$test_mode" == true ]; then
                            mail_message+="<p style=\"font-size: 13px; padding: 0 30px; color: darkgreen;\"><strong>TEST MODE ENABLED</strong></p>\n"
                        fi
                        mail_message+="<table border="0" style=\"font-size: 13px; padding: 0 30px;\">"
                            mail_message+="<tr>"
                                mail_message+="<td>Hostname:</td>"
                                mail_message+="<td>$hostname</td>"
                            mail_message+="</tr>"
                            mail_message+="<tr>"
                                mail_message+="<td>IP-Address:</td>"
                                mail_message+="<td>$primary_IPaddress</td>"
                            mail_message+="</tr>"
                            mail_message+="<tr>"
                                mail_message+="<td>Docker Version:</td>"
                                mail_message+="<td>$docker_version</td>"
                            mail_message+="</tr>"
                            mail_message+="<tr>"
                                mail_message+="<td>Script Version:</td>"
                                mail_message+="<td>$(Get-ScriptVersion)</td>"
                            mail_message+="</tr>"
                        mail_message+="</table>"
                        mail_message+="\n"

                        if [ -n "$mail_report_actions_taken" ]; then
                            mail_message+="<p style=\"font-size: 14px; padding-top: 15px; padding-left: 5px; color: #4b4b4b;\"><strong>&#x1F4CB; ACTIONS TAKEN</strong></p>\n"
                            mail_message+="<ul style=\"font-size: 13px; padding: 0px 50px;\">"
                                mail_message+="$mail_report_actions_taken"
                            mail_message+="</ul>"
                            mail_message+="\n"
                        fi

                        if [ -n "$mail_report_available_updates" ]; then
                            mail_message+="<p style=\"font-size: 14px; padding-top: 15px; padding-left: 5px; color: #4b4b4b;\"><strong>&#x1F527; OUTSTANDING UPDATES</strong></p>\n"
                            mail_message+="<table border="0" style=\"font-size: 13px; padding: 0 30px 15px;\">"
                                mail_message+="<tr>"
                                    mail_message+="<td><strong>Container Name</strong></td>"
                                    mail_message+="<td><strong>Update Type</strong></td>"
                                    mail_message+="<td><strong>Current Image</strong></td>"
                                    mail_message+="<td><strong>Available Image</strong></td>"
                                    mail_message+="<td><strong>Update Inhibitor Rule</strong></td>"
                                mail_message+="</tr>"
                                mail_message+="$mail_report_available_updates"
                            mail_message+="</table>"
                        fi

                        if [ -n "$mail_report_removed_container_backups" ]; then
                            mail_message+="<p style=\"font-size: 14px; padding-top: 15px; padding-left: 5px; color: #4b4b4b;\"><strong>&#128465;&#65039; REMOVED CONTAINER BACKUPS</strong></p>\n"
                            mail_message+="<ul style=\"font-size: 13px; padding: 0px 30px;\">"
                                mail_message+="$mail_report_removed_container_backups"
                            mail_message+="</ul>"
                            mail_message+="\n"
                        fi

                        mail_message+="<p style=\"font-size: 14px; padding-top: 15px; padding-left: 5px; color: #4b4b4b;\"><strong>&#x1F4C8; STATS</strong></p>\n"
                        mail_message+="<table border="0" style=\"font-size: 13px; padding: 0 30px 15px;\">"
                            mail_message+="<tr>"
                                mail_message+="<td>Script Execution Time:</td>"
                                mail_message+="<td>$stats_execution_time seconds</td>"
                            mail_message+="</tr>"
                            mail_message+="<tr>"
                                mail_message+="<td>Number of Warnings:</td>"
                                mail_message+="<td>$stats_warnings_count</td>"
                            mail_message+="</tr>"
                            mail_message+="<tr>"
                                mail_message+="<td>Number of Errors:</td>"
                                mail_message+="<td>$stats_errors_count</td>"
                            mail_message+="</tr>"
                        mail_message+="</table>"
                        mail_message+="\n"

                    mail_message+="</div>\n"
                    mail_message+="<p> </p>\n"
                    mail_message+="\n"
                    mail_message+="<p style=\"font-size: 10px;\"><i>For further information, please have a look into the provided log located in \"$logFile\". If you prefer not to receive these emails, please customize \"$configFile\" according to your specific requirements.</i></p>"
                    mail_message+="<p> </p>\n"
                    mail_message+="<p>Best regards.</p>"
                    mail_message+="\n"
                mail_message+="</body>\n"
            mail_message+="</html>\n"

            Write-Log "INFO" "        Saving generated mail report to \"$mail_message_file\"..."
                echo -e $mail_message > "$mail_message_file" || Write-Log "ERROR" "        Failed to create temporary mail message file (\"$mail_message_file\")"

            Write-Log "INFO" "        Sending notification via $mail_mode (\"$cmd_sendmail -t < $mail_message_file\")..."
                $cmd_sendmail -f "$mail_from" -t < "$mail_message_file"  2>/dev/null

            Write-Log "INFO" "        Removing temporary mail message file (\"$mail_message_file\")..."
                rm -f "$mail_message_file" 2>/dev/null || Write-Log "ERROR" "        Failed to delete temporary mail message file (\"$mail_message_file\")"
        done
    else
        Write-Log "INFO" "    There is nothing to report"
    fi
}

Send-TelegramNotification() {
    local message=$1
    local cmd_curl=$(Read-INI "$configFile" "paths" "curl")
    local cmd_jq=$(Read-INI "$configFile" "paths" "jq")
    local logFile=$(Read-INI "$configFile" "log" "filePath")
    local bot_token=$(Read-INI "$configFile" "telegram" "bot_token")
    local chat_id=$(Read-INI "$configFile" "telegram" "chat_id")
    local retry_interval=$(Read-INI "$configFile" "telegram" "retry_interval")
    local retry_limit=$(Read-INI "$configFile" "telegram" "retry_limit")
    local telegram_api_response=""
    local curl_response=""
    local telegram_sendMessage_command="$cmd_curl -s -X POST \"https://api.telegram.org/bot$bot_token/sendMessage\" -H \"Content-Type: application/json\" -d '{ \"chat_id\": "$chat_id", \"text\": \"$message\", \"parse_mode\": \"MarkdownV2\" }'"

    for ((i = 1; i <= retry_limit; i++)); do

        Write-Log "INFO"  "        Sending telegram message to chat ID \"$chat_id\" with \"$bot_token\" (Attempt $i of $retry_limit)..."
        Write-Log "DEBUG" "          => Bot Token:       \"$bot_token\""
        Write-Log "DEBUG" "          => Chat ID:         \"$chat_id\""
        Write-Log "DEBUG" "          => Message Length:  $(Telegram-GetMessageLength \""$message"\")"
        Write-Log "DEBUG" "          => Message Content: \"$message\""
        Write-Log "DEBUG" "          => Command:         \"$telegram_sendMessage_command\""
        telegram_api_response=$($cmd_curl -s -X POST "https://api.telegram.org/bot$bot_token/sendMessage" -H "Content-Type: application/json" -d '{ "chat_id": "'$chat_id'", "text": "'"$message"'", "parse_mode": "MarkdownV2" }')

        if [ "$(echo "$telegram_api_response" | $cmd_jq -r '.ok')" = "true" ]; then
            Write-Log "DEBUG" "          => Successfully sent message: $telegram_api_response"
            break
        else
            if [ -z "$telegram_api_response" ]; then
                curl_response=$($cmd_curl -Isv "https://api.telegram.org/")
                Write-Log "ERROR" "          => Failed to send message: $curl_response"
            else
                Write-Log "ERROR" "          => Failed to send message: $telegram_api_response"
            fi

            if ((i < retry_limit)); then
                Write-Log "INFO"  "          => Retry in $retry_interval seconds..."
                sleep "$retry_interval"
            fi
        fi
    done
}

Main() {
    Write-Log "INFO"  "<print_line_top>"
    Write-Log "INFO"  "║  GENERAL INFORMATION"
    Write-Log "INFO"  "<print_line_btn>"
    Write-Log "INFO" "    Version:      $(Get-ScriptVersion)"
    [[ "$test_mode" == true  ]] && Write-Log "INFO" "    Test Mode:    Enabled"
    [[ "$test_mode" == false ]] && Write-Log "INFO" "    Test Mode:    Disabled"
    Write-Log "INFO" "    Log Level:    $logLevel"

    local test_mode=$test_mode
    local mail_notifications_enabled=$(Read-INI "$configFile" "mail" "notifications_enabled")
    local telegram_notifications_enabled=$(Read-INI "$configFile" "telegram" "notifications_enabled")
    local cmd_sed=$(Read-INI "$configFile" "paths" "sed")
    local cmd_jq=$(Read-INI "$configFile" "paths" "jq")
    local cmd_docker=$(Read-INI "$configFile" "paths" "docker")
    local cmd_date=$(Read-INI "$configFile" "paths" "date")
    local container_ids=($($cmd_docker ps -q $1))
    local container_id=""
    local container_config=""
    local container_name=""
    local container_hostname=""
    local container_state_paused=""
    local container_hostname=""
    local container_labels=""
    local container_labels_unique=""
    local container_capabilities=""
    local container_networkMode=""
    local container_networkMode_IPv4Address=""
    local container_networkMode_IPv6Address=""
    local container_networkMode_MacAddress=""
    local container_primaryNetwork_Name=""
    local container_primaryNetwork_IPv4Address=""
    local container_primaryNetwork_IPv6Address=""
    local container_primaryNetwork_MacAddress=""
    local container_restartPolicy_name=""
    local container_restartPolicy_MaximumRetryCount=""
    local container_PublishAllPorts=""
    local container_Privileged=""
    local container_Tty=""
    local container_PortBindings=""
    local container_Mounts=""
    local container_envs=""
    local container_envs_unique=""
    local container_tmpfs=""
    local container_cmd=""
    local container_image_id=""
    local container_image_name=""
    local container_image_tag=""
    local container_hostname=""
    local image_config=""
    local image_labels=""
    local image_envs=""
    local image_cmd=""
    local image_repoDigests=""
    local effective_update_rule=""
    local docker_hub_image_url=""
    local docker_hub_image_tags=""
    local docker_hub_image_tag_names=""
    local docker_hub_image_tag_names_filter=""
    local docker_hub_image_tag_names_filtered=""
    local docker_hub_image_tag_names_filtered_and_sorted=""
    local docker_hub_image_tag_names_filtered_and_sorted_by_major=""
    local docker_hub_image_tag_names_filtered_and_sorted_by_minor=""
    local docker_hub_image_tag_names_filtered_and_sorted_by_patch=""
    local docker_hub_image_tag_names_filtered_and_sorted_by_build=""
    local docker_hub_image_tag_digest=""
    local docker_hub_image_tag_last_updated=""
    local docker_hub_image_tag_age=""
    local image_updates_available_all=""
    local image_update_available_major_next=""
    local image_update_available_minor_next=""
    local image_update_available_patch_next=""
    local image_update_available_build_next=""
    local image_update_available_major_latest=""
    local image_update_available_minor_latest=""
    local image_update_available_patch_latest=""
    local image_update_available_build_latest=""
    local image_update_available_digest=""
    local updatePermit=""
    local updatePerformed=""


    if [ ${#container_ids[@]} -gt 0 ]; then
        for container_id in "${container_ids[@]}"; do
            container_name=""
            container_hostname=""
            container_state_paused=""
            container_labels=""
            container_labels_unique=""
            container_capabilities=""
            container_networkMode=""
            container_networkMode_IPv4Address=""
            container_networkMode_IPv6Address=""
            container_networkMode_MacAddress=""
            container_primaryNetwork_Name=""
            container_primaryNetwork_IPv4Address=""
            container_primaryNetwork_IPv6Address=""
            container_primaryNetwork_MacAddress=""
            container_restartPolicy_name=""
            container_restartPolicy_MaximumRetryCount=""
            container_PublishAllPorts=""
            container_Privileged=""
            container_Tty=""
            container_PortBindings=""
            container_Mounts=""
            container_envs=""
            container_envs_unique=""
            container_tmpfs=""
            container_cmd=""
            container_image_name=""
            container_image_id=""
            image_labels=""
            image_envs=""
            image_cmd=""
            container_image_tag=""
            image_tag_version_major=""
            image_tag_version_minor=""
            image_tag_version_patch=""
            image_tag_version_build=""
            image_repoDigests=""
            docker_hub_image_url=""
            container_config=""
            image_config=""
            docker_hub_image_tags=""
            docker_hub_image_tag_digest=""
            docker_hub_image_tag_last_updated=""
            docker_hub_image_tag_age=""
            docker_hub_image_tag_names_filter=""
            docker_hub_image_tag_names=""
            effective_update_rule=""
            image_updates_available_all=""
            image_update_available_digest=false
            image_update_available_build_next=""
            image_update_available_patch_next=""
            image_update_available_minor_next=""
            image_update_available_major_next=""
            image_update_available_build_latest=""
            image_update_available_patch_latest=""
            image_update_available_minor_latest=""
            image_update_available_major_latest=""
            updatePermit=false
            updatePerformed=false

            Write-Log "INFO" "<print_line_top>"
            Write-Log "INFO" "║ PROCESSING CONTAINER $container_id"
            Write-Log "INFO" "<print_line_btn>"
            Write-Log "INFO" "    Requesting container configuration by executing \"$cmd_docker container inspect "$container_id"\"..."
            container_config=$(echo "$($cmd_docker container inspect "$container_id")" | tr -d '\n') #json
            container_image_id=$(Get-ContainerProperty "$container_config" container_image_id)
            Write-Log "INFO" "    Requesting image details by executing \"$cmd_docker image inspect $container_image_id\"..."
            image_config=$(echo "$($cmd_docker image inspect $container_image_id)" | tr -d '\n') #json
            docker_run_command_creation_completed=false
            container_name=$(Get-ContainerProperty "$container_config" container_name)
            container_hostname=$(Get-ContainerProperty "$container_config" container_hostname)
            container_state_paused=$(Get-ContainerProperty "$container_config" container_state_paused)
            container_labels=$(Get-ContainerProperty "$container_config" container_labels)
            container_capabilities=$(Get-ContainerProperty "$container_config" container_capabilities)
            container_networkMode=$(Get-ContainerProperty "$container_config" container_networkMode)
            container_networkMode_IPv4Address=$(Get-ContainerProperty "$container_config" container_networkMode_IPv4Address)
            container_networkMode_IPv6Address=$(Get-ContainerProperty "$container_config" container_networkMode_IPv6Address)
            container_networkMode_MacAddress=$(Get-ContainerProperty "$container_config" container_networkMode_MacAddress)
            container_primaryNetwork_Name=$(Get-ContainerProperty "$container_config" container_primaryNetwork_Name)
            container_primaryNetwork_IPv4Address=$(Get-ContainerProperty "$container_config" container_primaryNetwork_IPv4Address)
            container_primaryNetwork_IPv6Address=$(Get-ContainerProperty "$container_config" container_primaryNetwork_IPv6Address)
            container_primaryNetwork_MacAddress=$(Get-ContainerProperty "$container_config" container_primaryNetwork_MacAddress)
            container_restartPolicy_name=$(Get-ContainerProperty "$container_config" container_restartPolicy_name)
            container_restartPolicy_MaximumRetryCount=$(Get-ContainerProperty "$container_config" container_restartPolicy_MaximumRetryCount)
            container_PublishAllPorts=$(Get-ContainerProperty "$container_config" container_PublishAllPorts)
            container_Privileged=$(Get-ContainerProperty "$container_config" container_Privileged)
            container_Tty=$(Get-ContainerProperty "$container_config" container_Tty)
            container_PortBindings=$(Get-ContainerProperty "$container_config" container_PortBindings)
            container_Mounts=$(Get-ContainerProperty "$container_config" container_Mounts)
            container_envs=$(Get-ContainerProperty "$container_config" container_envs)
            container_tmpfs=$(Get-ContainerProperty "$container_config" container_tmpfs)
            container_cmd=$(Get-ContainerProperty "$container_config" container_cmd)
            container_image_name=$(Get-ContainerProperty "$container_config" container_image_name)
            container_image_tag=$(Get-ContainerProperty "$container_config" container_image_tag)
            image_repoDigests=$(Get-ImageProperty "$image_config" image_repoDigests)
            image_labels=$(Get-ImageProperty "$image_config" image_labels)
            image_envs=$(Get-ImageProperty "$image_config" image_envs)
            image_cmd=$(Get-ImageProperty "$image_config" image_cmd)
            image_tag_version_major=$(Extract-VersionPart "$container_image_tag" "major")
            image_tag_version_minor=$(Extract-VersionPart "$container_image_tag" "minor")
            image_tag_version_patch=$(Extract-VersionPart "$container_image_tag" "patch")
            image_tag_version_build=$(Extract-VersionPart "$container_image_tag" "build")
            effective_update_rule=$(Get-EffectiveUpdateRule "$container_name")
            container_labels_unique=$(Get-ContainerPropertyUnique "$container_labels" "$image_labels" "unique_labels")
            container_envs_unique=$(Get-ContainerPropertyUnique "$container_envs" "$image_envs" "unique_envs")
            docker_hub_image_url=$(Get-ImageURL "$container_image_name")
            docker_hub_image_tag_names_filter=$(New-DockerHubImageTagFilter "$container_image_tag")

            # To be able to report available and outstanding updates for containers/images, this if-statement ist commented out
            #if [[ ! $effective_update_rule == *"[0.0.0-0,false]"* ]]; then
            Write-Log "INFO"  "    Requesting available image tags from Docker Hub..."
            docker_hub_image_tags=$(Get-DockerHubImageTags "$container_image_name") #json
            [ -z "$docker_hub_image_tags" ] && Write-Log "ERROR" "    => Failed to request available image tags: wget $docker_hub_image_url/tags"
            #else
            #    Write-Log "INFO"  "    Request of available image tags from Docker Hub is restricted by specified update rule \"$effective_update_rule\""
            #    docker_hub_image_tags=""
            #fi

            if [ -n "$docker_hub_image_tags" ]; then
                Write-Log "INFO"  "    Extracting a list of available image tag names..."
                docker_hub_image_tag_digest=$(Get-DockerHubImageTagProperty "$docker_hub_image_tags" "$container_image_tag" "docker_hub_image_tag_digest")
                docker_hub_image_tag_last_updated=$(Get-DockerHubImageTagProperty "$docker_hub_image_tags" "$container_image_tag" "docker_hub_image_tag_last_updated")
                [ -n "$docker_hub_image_tag_last_updated" ] && docker_hub_image_tag_age=$(( $(date +%s) - $($cmd_date -d "$docker_hub_image_tag_last_updated" +%s) ))
                docker_hub_image_tag_names=$(Get-DockerHubImageTagNames "$docker_hub_image_tags")
                image_updates_available_all=$(Get-AvailableUpdates "all" "$docker_hub_image_tag_names" "$docker_hub_image_tag_names_filter" "$container_image_tag")
                [ -n "$docker_hub_image_tag_digest" ] && image_update_available_digest=$(Get-AvailableUpdates "digest" "$image_repoDigests" "$docker_hub_image_tag_digest")
                [ -n "$image_tag_version_major" ] && image_update_available_major_next=$(Get-AvailableUpdates "major" "$image_updates_available_all" "$container_image_tag" "next")
                [ -n "$image_tag_version_major" ] && image_update_available_major_latest=$(Get-AvailableUpdates "major" "$image_updates_available_all" "$container_image_tag" "latest")
                [ -n "$image_tag_version_minor" ] && image_update_available_minor_next=$(Get-AvailableUpdates "minor" "$image_updates_available_all" "$container_image_tag" "next")
                [ -n "$image_tag_version_minor" ] && image_update_available_minor_latest=$(Get-AvailableUpdates "minor" "$image_updates_available_all" "$container_image_tag" "latest")
                [ -n "$image_tag_version_patch" ] && image_update_available_patch_next=$(Get-AvailableUpdates "patch" "$image_updates_available_all" "$container_image_tag" "next")
                [ -n "$image_tag_version_patch" ] && image_update_available_patch_latest=$(Get-AvailableUpdates "patch" "$image_updates_available_all" "$container_image_tag" "latest")
                [ -n "$image_tag_version_build" ] && image_update_available_build_next=$(Get-AvailableUpdates "build" "$image_updates_available_all" "$container_image_tag" "next")
                [ -n "$image_tag_version_build" ] && image_update_available_build_latest=$(Get-AvailableUpdates "build" "$image_updates_available_all" "$container_image_tag" "latest")
            elif [ -z "$docker_hub_image_tags" ] || [[ $effective_update_rule == *"[0.0.0-0,false]"* ]]; then
                docker_hub_image_tag_digest=""
                docker_hub_image_tag_last_updated=""
                docker_hub_image_tag_age=""
                docker_hub_image_tag_names=""
                image_update_available_major_next=""
                image_update_available_major_latest=""
                image_update_available_minor_next=""
                image_update_available_minor_latest=""
                image_update_available_patch_next=""
                image_update_available_patch_latest=""
                image_update_available_build_next=""
                image_update_available_build_latest=""
                image_update_available_digest=""
            fi

            Write-Log "INFO"  "    <print_line_top>"
            Write-Log "INFO"  "    ║ CONTAINER AND IMAGE DETAILS"
            Write-Log "INFO"  "    <print_line_btn>"
            Write-Log "INFO"  "       Container Name:                                       $container_name"
            Write-Log "DEBUG" "       Container Hostname:                                   $container_hostname"
            Write-Log "DEBUG" "       Container Is Paused:                                  $container_state_paused"
            Write-Log "DEBUG" "       Container ID:                                         $container_id"
            Write-Log "DEBUG" "       Container Labels:                                     $container_labels"
            Write-Log "DEBUG" "       Container Labels (Unique):                            $container_labels_unique"
            Write-Log "DEBUG" "       Container Capabilities:                               $container_capabilities"
            Write-Log "DEBUG" "       Container Network Mode:                               $container_networkMode"
            Write-Log "DEBUG" "       Container Primary Network Name:                       $container_primaryNetwork_Name"
            Write-Log "DEBUG" "       Container Primary IPv4-Address:                       $container_primaryNetwork_IPv4Address"
            Write-Log "DEBUG" "       Container Primary IPv6-Address:                       $container_primaryNetwork_IPv6Address"
            Write-Log "DEBUG" "       Container Primary MAC-Address:                        $container_primaryNetwork_MacAddress"
            Write-Log "DEBUG" "       Container Network Mode IPv4-Address:                  $container_networkMode_IPv4Address"
            Write-Log "DEBUG" "       Container Network Mode IPv6-Address:                  $container_networkMode_IPv6Address"
            Write-Log "DEBUG" "       Container Network Mode MAC-Address:                   $container_networkMode_MacAddress"
            Write-Log "DEBUG" "       Container Restart Policy Name:                        $container_restartPolicy_name"
            Write-Log "DEBUG" "       Container Maximum Retry Count:                        $container_restartPolicy_MaximumRetryCount"
            Write-Log "DEBUG" "       Container Publish All Ports:                          $container_PublishAllPorts"
            Write-Log "DEBUG" "       Container Privileged:                                 $container_Privileged"
            Write-Log "DEBUG" "       Container TTY:                                        $container_Tty"
            Write-Log "DEBUG" "       Container Port Bindings:                              $container_PortBindings"
            Write-Log "DEBUG" "       Container Mounts:                                     $container_Mounts"
            Write-Log "DEBUG" "       Container Environment Variables:                      $container_envs"
            Write-Log "DEBUG" "       Container Environment Variables (Unique):             $container_envs_unique"
            Write-Log "DEBUG" "       Container Temporary File Systems:                     $container_tmpfs"
            Write-Log "DEBUG" "       Container Command:                                    $container_cmd"
            Write-Log "INFO"  "       Image Name:                                           $container_image_name"
            Write-Log "DEBUG" "       Image ID:                                             $container_image_id"
            Write-Log "DEBUG" "       Image Labels:                                         $image_labels"
            Write-Log "DEBUG" "       Image Environment Variables:                          $image_envs"
            Write-Log "DEBUG" "       Image Command:                                        $image_cmd"
            Write-Log "INFO"  "       Image Tag:                                            $container_image_tag"
            Write-Log "DEBUG" "       Image Tag Ver. (Major):                               $image_tag_version_major"
            Write-Log "DEBUG" "       Image Tag Ver. (Minor):                               $image_tag_version_minor"
            Write-Log "DEBUG" "       Image Tag Ver. (Patch):                               $image_tag_version_patch"
            Write-Log "DEBUG" "       Image Tag Ver. (Build):                               $image_tag_version_build"
            Write-Log "DEBUG" "       Image Repository Digests:                             $image_repoDigests"
            Write-Log "INFO"  "       Image URL:                                            $docker_hub_image_url"
            Write-Log "DEBUG" "       Container Details (json):                             $container_config"
            Write-Log "DEBUG" "       Image Details (json):                                 $image_config"
            [ -n "$docker_hub_image_tags" ] && Write-Log "DEBUG" "       Docker Hub Image Tags (json):                         $docker_hub_image_tags"
            [ -n "$docker_hub_image_tags" ] && Write-Log "DEBUG" "       Docker Hub Image Digest:                              $docker_hub_image_tag_digest"
            [ -n "$docker_hub_image_tags" ] && Write-Log "DEBUG" "       Docker Hub Image Last Updated:                        $docker_hub_image_tag_last_updated"
            [ -n "$docker_hub_image_tags" ] && Write-Log "DEBUG" "       Docker Hub Image Age:                                 $docker_hub_image_tag_age${docker_hub_image_tag_age:+ Seconds}"
            [ -n "$docker_hub_image_tags" ] && Write-Log "DEBUG" "       Docker Hub Image Tag Filter:                          $docker_hub_image_tag_names_filter"
            [ -n "$docker_hub_image_tags" ] && Write-Log "DEBUG" "       Docker Hub Image Tag Names:                           $docker_hub_image_tag_names"
            [ -n "$docker_hub_image_tags" ] && Write-Log "INFO"  "       Update Overview:"
            [ -n "$docker_hub_image_tags" ] && Write-Log "DEBUG" "             Effective Update Rule:                          $effective_update_rule"
            [ -n "$docker_hub_image_tags" ] && Write-Log "DEBUG" "             Listing (filtered & sorted):                    $image_updates_available_all"
            [ -n "$docker_hub_image_tags" ] && Write-Log "INFO"  "             New Digest available:                           $image_update_available_digest"
            [ -n "$docker_hub_image_tags" ] && Write-Log "INFO"  "             Next Build:                                     $image_update_available_build_next"
            [ -n "$docker_hub_image_tags" ] && Write-Log "INFO"  "             Next Patch:                                     $image_update_available_patch_next"
            [ -n "$docker_hub_image_tags" ] && Write-Log "INFO"  "             Next Minor:                                     $image_update_available_minor_next"
            [ -n "$docker_hub_image_tags" ] && Write-Log "INFO"  "             Next Major:                                     $image_update_available_major_next"
            [ -n "$docker_hub_image_tags" ] && Write-Log "INFO"  "             Latest Build:                                   $image_update_available_build_latest"
            [ -n "$docker_hub_image_tags" ] && Write-Log "INFO"  "             Latest Patch:                                   $image_update_available_patch_latest"
            [ -n "$docker_hub_image_tags" ] && Write-Log "INFO"  "             Latest Minor:                                   $image_update_available_minor_latest"
            [ -n "$docker_hub_image_tags" ] && Write-Log "INFO"  "             Latest Major:                                   $image_update_available_major_latest"

            # Create docker run command (without specifying the image tag for the moment)
                                                                                                docker_run_cmd="$cmd_docker run -d"
            [ -n "$container_name" ] &&                                                         docker_run_cmd+=" --name=$container_name"
            [ -n "$container_hostname" ] &&                                                     docker_run_cmd+=" --hostname=$container_hostname"
            [ -n "$container_restartPolicy_name" ] &&                                           docker_run_cmd+=" --restart=$container_restartPolicy_name"
            [ -n "$container_networkMode" ] &&                                                  docker_run_cmd+=" --network=$container_networkMode"
            [ -n "$container_networkMode_IPv4Address" ] &&                                      docker_run_cmd+=" --ip=$container_networkMode_IPv4Address"
            [ -n "$container_networkMode_IPv6Address" ] &&                                      docker_run_cmd+=" --ip6=$container_networkMode_IPv6Address"
            [ -n "$container_PublishAllPorts" ] && [ "$container_PublishAllPorts" == true ] &&  docker_run_cmd+=" --publish-all"
            [ -n "$container_Privileged" ] && [ "$container_Privileged" == true ] &&            docker_run_cmd+=" --privileged"
            [ -n "$container_Tty" ] && [ "$container_Tty" == true ] &&                          docker_run_cmd+=" --tty"
            [ -n "$container_capabilities" ] &&                                                 docker_run_cmd+=" $container_capabilities"
            [ -n "$container_PortBindings" ] &&                                                 docker_run_cmd+=" $container_PortBindings"
            [ -n "$container_Mounts" ] &&                                                       docker_run_cmd+=" $container_Mounts"
            [ -n "$container_envs_unique" ] &&                                                  docker_run_cmd+=" $container_envs_unique"
            [ -n "$container_tmpfs" ] &&                                                        docker_run_cmd+=" $container_tmpfs"
            [ -n "$container_labels_unique" ] &&                                                docker_run_cmd+=" $container_labels_unique"
            [ -n "$container_image_name" ] &&                                                   docker_run_cmd+=" $container_image_name"

            # Perform a digest update if available and update permission is granted by update rule definition
            if [ -n "$container_name" ] && [ -n "$container_image_tag" ] && [ "$image_update_available_digest" == true ]; then
                updatePermit=$(Get-UpdatePermit "$container_name" "$container_image_tag" "$container_image_tag")
                if [ "$updatePermit" == true ]; then
                    if { [[ -n "$docker_hub_image_tag_age" ]] && [ "$docker_hub_image_tag_age" -gt "$(Read-INI "$configFile" "general" "docker_hub_image_minimum_age")" ]; } || [ -z "$docker_hub_image_tag_age" ]; then
                        if [ "$updatePerformed" == false ]; then
                            [ -n "$container_image_tag" ] &&    docker_run_cmd+=":$container_image_tag"
                            #[ -n "$container_cmd" ] &&          docker_run_cmd+=" $container_cmd"
                            Perform-ImageUpdate "digest" "$container_name" "$container_state_paused" "$container_restartPolicy_name" "$container_image_name" "$docker_run_cmd" "$container_image_tag"
                            updatePerformed=true
                        else
                            Write-Log "DEBUG" "       This update cannot be performed yet, because another update has been already performed previously"
                            mail_report_available_updates+="<tr><td>$container_name</td><td>Digest</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$container_image_tag</td><td></td></tr>"
                            telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$container_image_tag")\n"
                            report_available=true
                        fi
                    else
                        Write-Log "INFO"  "       Insufficient Docker Hub image age"
                        Write-Log "DEBUG" "        => The age of the image available on Docker Hub is less than the configured minimum age of $(Read-INI "$configFile" "general" "docker_hub_image_minimum_age") seconds"
                        mail_report_available_updates+="<tr><td>$container_name</td><td>Digest</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$container_image_tag</td><td>$effective_update_rule</td></tr>"
                        telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$container_image_tag")\n"
                        report_available=true
                    fi
                else
                    Write-Log "INFO" "       Update Rule Effectivity:                              Digest update for $container_name ($container_image_name:$container_image_tag) was prevented"
                    mail_report_available_updates+="<tr><td>$container_name</td><td>Digest</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$container_image_tag</td><td>$effective_update_rule</td></tr>"
                    telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$container_image_tag")\n"
                    report_available=true
                fi
            fi

            # Perform a build update if available and update permission is granted by update rule definition
            if [ -n "$container_name" ] && [ -n "$container_image_tag" ] && [ -n "$image_update_available_build_next" ] && [ -n "$image_update_available_build_latest" ]; then
                updatePermit=$(Get-UpdatePermit "$container_name" "$container_image_tag" "$image_update_available_build_next" "$image_update_available_build_latest")
                if [ "$updatePermit" == true ]; then
                    if { [[ -n "$docker_hub_image_tag_age" ]] && [ "$docker_hub_image_tag_age" -gt "$(Read-INI "$configFile" "general" "docker_hub_image_minimum_age")" ]; } || [ -z "$docker_hub_image_tag_age" ]; then
                        if [ "$updatePerformed" == false ]; then
                            [ -n "$container_image_tag" ] &&    docker_run_cmd+=":$image_update_available_build_next"
                            #[ -n "$container_cmd" ] &&          docker_run_cmd+=" $container_cmd"
                            Perform-ImageUpdate "build" "$container_name" "$container_state_paused" "$container_restartPolicy_name" "$container_image_name" "$docker_run_cmd" "$container_image_tag" "$image_update_available_build_next"
                            updatePerformed=true
                            container_config=$(echo $($cmd_docker container inspect "$container_name") | tr -d '\n') #json
                            container_image_tag=$(Get-ContainerProperty "$container_config" container_image_tag)
                            image_update_available_build_next=$(Get-AvailableUpdates "patch" "$image_updates_available_all" "$container_image_tag" "next")
                            if [ -n "$image_update_available_build_next" ]; then
                                mail_report_available_updates+="<tr><td>$container_name</td><td>Patch</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_build_next</td><td></td></tr>"
                                telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_build_next")\n"
                                report_available=true
                            fi
                        else
                            Write-Log "DEBUG" "       This update cannot be performed yet, because another update has been already performed previously"
                            mail_report_available_updates+="<tr><td>$container_name</td><td>Build</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_build_next</td><td></td></tr>"
                            telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_build_next")\n"
                            report_available=true
                        fi
                    else
                        Write-Log "INFO"  "       Insufficient Docker Hub image age"
                        Write-Log "DEBUG" "        => The age of the image available on Docker Hub is less than the configured minimum age of $(Read-INI "$configFile" "general" "docker_hub_image_minimum_age") seconds"
                        mail_report_available_updates+="<tr><td>$container_name</td><td>Patch</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_build_next</td><td></td></tr>"
                        telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_build_next")\n"
                        report_available=true
                    fi
                else
                    Write-Log "INFO" "       Update Rule Effectivity:                              Build update for $container_name ($container_image_name:$container_image_tag to $container_image_name:$image_update_available_build_next) was prevented"
                    mail_report_available_updates+="<tr><td>$container_name</td><td>Build</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_build_next</td><td>$effective_update_rule</td></tr>"
                    telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_build_next")\n"
                    report_available=true
                fi
            fi

            # Perform a patch update if available and update permission is granted by update rule definition
            if [ -n "$container_name" ] && [ -n "$container_image_tag" ] && [ -n "$image_update_available_patch_next" ] && [ -n "$image_update_available_patch_latest" ]; then
                updatePermit=$(Get-UpdatePermit "$container_name" "$container_image_tag" "$image_update_available_patch_next" "$image_update_available_patch_latest")
                if [ "$updatePermit" == true ]; then
                    if { [[ -n "$docker_hub_image_tag_age" ]] && [ "$docker_hub_image_tag_age" -gt "$(Read-INI "$configFile" "general" "docker_hub_image_minimum_age")" ]; } || [ -z "$docker_hub_image_tag_age" ]; then
                        if [ "$updatePerformed" == false ]; then
                            [ -n "$container_image_tag" ] &&    docker_run_cmd+=":$image_update_available_patch_next"
                            #[ -n "$container_cmd" ] &&          docker_run_cmd+=" $container_cmd"
                            Perform-ImageUpdate "patch" "$container_name" "$container_state_paused" "$container_restartPolicy_name" "$container_image_name" "$docker_run_cmd" "$container_image_tag" "$image_update_available_patch_next"
                            updatePerformed=true
                            container_config=$(echo $($cmd_docker container inspect "$container_name") | tr -d '\n') #json
                            container_image_tag=$(Get-ContainerProperty "$container_config" container_image_tag)
                            image_update_available_patch_next=$(Get-AvailableUpdates "patch" "$image_updates_available_all" "$container_image_tag" "next")
                            if [ -n "$image_update_available_patch_next" ]; then
                                mail_report_available_updates+="<tr><td>$container_name</td><td>Patch</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_patch_next</td><td></td></tr>"
                                telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_patch_next")\n"
                                report_available=true
                            fi
                        else
                            Write-Log "DEBUG" "       This update cannot be performed yet, because another update has been already performed previously"
                            mail_report_available_updates+="<tr><td>$container_name</td><td>Patch</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_patch_next</td><td></td></tr>"
                            telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_patch_next")\n"
                            report_available=true
                        fi
                    else
                        Write-Log "INFO"  "       Insufficient Docker Hub image age"
                        Write-Log "DEBUG" "        => The age of the image available on Docker Hub is less than the configured minimum age of $(Read-INI "$configFile" "general" "docker_hub_image_minimum_age") seconds"
                        mail_report_available_updates+="<tr><td>$container_name</td><td>Patch</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_patch_next</td><td></td></tr>"
                        telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_patch_next")\n"
                        report_available=true
                    fi
                else
                    Write-Log "INFO" "       Update Rule Effectivity:                              Patch update for $container_name ($container_image_name:$container_image_tag to $container_image_name:$image_update_available_patch_next) was prevented"
                    mail_report_available_updates+="<tr><td>$container_name</td><td>Patch</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_patch_next</td><td>$effective_update_rule</td></tr>"
                    telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_patch_next")\n"
                    report_available=true
                fi
            fi

            # Perform a minor update if available and update permission is granted by update rule definition
            if [ -n "$container_name" ] && [ -n "$container_image_tag" ] && [ -n "$image_update_available_minor_next" ] && [ -n "$image_update_available_minor_latest" ]; then
                updatePermit=$(Get-UpdatePermit "$container_name" "$container_image_tag" "$image_update_available_minor_next" "$image_update_available_minor_latest")
                if [ "$updatePermit" == true ]; then
                    if { [[ -n "$docker_hub_image_tag_age" ]] && [ "$docker_hub_image_tag_age" -gt "$(Read-INI "$configFile" "general" "docker_hub_image_minimum_age")" ]; } || [ -z "$docker_hub_image_tag_age" ]; then
                        if [ "$updatePerformed" == false ]; then
                            [ -n "$container_image_tag" ] &&    docker_run_cmd+=":$image_update_available_minor_next"
                            #[ -n "$container_cmd" ] &&          docker_run_cmd+=" $container_cmd"
                            Perform-ImageUpdate "minor" "$container_name" "$container_state_paused" "$container_restartPolicy_name" "$container_image_name" "$docker_run_cmd" "$container_image_tag" "$image_update_available_minor_next"
                            updatePerformed=true
                            container_config=$(echo $($cmd_docker container inspect "$container_name") | tr -d '\n') #json
                            container_image_tag=$(Get-ContainerProperty "$container_config" container_image_tag)
                            image_update_available_minor_next=$(Get-AvailableUpdates "patch" "$image_updates_available_all" "$container_image_tag" "next")
                            if [ -n "$image_update_available_minor_next" ]; then
                                mail_report_available_updates+="<tr><td>$container_name</td><td>Patch</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_minor_next</td><td></td></tr>"
                                telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_minor_next")\n"
                                report_available=true
                            fi
                        else
                            Write-Log "DEBUG" "       This update cannot be performed yet, because another update has been already performed previously"
                            mail_report_available_updates+="<tr><td>$container_name</td><td>Minor</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_minor_next</td><td></td></tr>"
                            telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_minor_next")\n"
                            report_available=true
                        fi
                    else
                        Write-Log "INFO"  "       Insufficient Docker Hub image age"
                        Write-Log "DEBUG" "        => The age of the image available on Docker Hub is less than the configured minimum age of $(Read-INI "$configFile" "general" "docker_hub_image_minimum_age") seconds"
                        mail_report_available_updates+="<tr><td>$container_name</td><td>Patch</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_minor_next</td><td></td></tr>"
                        telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_minor_next")\n"
                        report_available=true
                    fi
                else
                    Write-Log "INFO" "       Update Rule Effectivity:                              Minor update for $container_name ($container_image_name:$container_image_tag to $container_image_name:$image_update_available_minor_next) was prevented"
                    mail_report_available_updates+="<tr><td>$container_name</td><td>Minor</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_minor_next</td><td>$effective_update_rule</td></tr>"
                    telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_minor_next")\n"
                    report_available=true
                fi
            fi

            # Perform a major update if available and update permission is granted by update rule definition
            if [ -n "$container_name" ] && [ -n "$container_image_tag" ] && [ -n "$image_update_available_major_next" ] && [ -n "$image_update_available_major_latest" ]; then
                updatePermit=$(Get-UpdatePermit "$container_name" "$container_image_tag" "$image_update_available_major_next" "$image_update_available_major_latest")
                if [ "$updatePermit" == true ]; then
                    if { [[ -n "$docker_hub_image_tag_age" ]] && [ "$docker_hub_image_tag_age" -gt "$(Read-INI "$configFile" "general" "docker_hub_image_minimum_age")" ]; } || [ -z "$docker_hub_image_tag_age" ]; then
                        if [ "$updatePerformed" == false ]; then
                            [ -n "$container_image_tag" ] &&    docker_run_cmd+=":$image_update_available_major_next"
                            #[ -n "$container_cmd" ] &&          docker_run_cmd+=" $container_cmd"
                            Perform-ImageUpdate "major" "$container_name" "$container_state_paused" "$container_restartPolicy_name" "$container_image_name" "$docker_run_cmd" "$container_image_tag" "$image_update_available_major_next"
                            updatePerformed=true
                            container_config=$(echo $($cmd_docker container inspect "$container_name") | tr -d '\n') #json
                            container_image_tag=$(Get-ContainerProperty "$container_config" container_image_tag)
                            image_update_available_major_next=$(Get-AvailableUpdates "patch" "$image_updates_available_all" "$container_image_tag" "next")
                            if [ -n "$image_update_available_major_next" ]; then
                                mail_report_available_updates+="<tr><td>$container_name</td><td>Patch</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_major_next</td><td></td></tr>"
                                telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_major_next")\n"
                                report_available=true
                            fi
                        else
                            Write-Log "DEBUG" "       This update cannot be performed yet, because another update has been already performed previously"
                            mail_report_available_updates+="<tr><td>$container_name</td><td>Major</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_major_next</td><td></td></tr>"
                            telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_major_next")\n"
                            report_available=true
                        fi
                    else
                        Write-Log "INFO"  "       Insufficient Docker Hub image age"
                        Write-Log "DEBUG" "        => The age of the image available on Docker Hub is less than the configured minimum age of $(Read-INI "$configFile" "general" "docker_hub_image_minimum_age") seconds"
                        mail_report_available_updates+="<tr><td>$container_name</td><td>Patch</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_major_next</td><td></td></tr>"
                        telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_major_next")\n"
                        report_available=true
                    fi
                else
                    Write-Log "INFO" "       Update Rule Effectivity:                              Major update for $container_name ($container_image_name:$container_image_tag to $container_image_name:$image_update_available_major_next) was prevented"
                    mail_report_available_updates+="<tr><td>$container_name</td><td>Major</td><td>$container_image_name:$container_image_tag</td><td>$container_image_name:$image_update_available_major_next</td><td>$effective_update_rule</td></tr>"
                    telegram_report_available_updates+="$(Telegram-EscapeSpecialChars "$container_name") \\\\($(Telegram-EscapeSpecialChars "$container_image_name")\\\\): $(Telegram-EscapeSpecialChars "$image_update_available_major_next")\n"
                    report_available=true
                fi
            fi
        done

        if [ "$test_mode" == false ]; then
            Write-Log "INFO"  "<print_line_top>"
            Write-Log "INFO"  "║  PRUNING PROGRESS"
            Write-Log "INFO"  "<print_line_btn>"
            Prune-ContainerBackups
            Prune-DockerImages
        fi

        if [ "$mail_notifications_enabled" == true ]; then
            Write-Log "INFO" "<print_line_top>"
            Write-Log "INFO" "║ MAIL NOTIFICATIONS"
            Write-Log "INFO" "<print_line_btn>"
            Send-MailNotification
        fi

        if [ "$telegram_notifications_enabled" == true ]; then
            Write-Log "INFO" "<print_line_top>"
            Write-Log "INFO" "║ TELEGRAM NOTIFICATIONS"
            Write-Log "INFO" "<print_line_btn>"
            Telegram-SplitMessage "$(Telegram-GenerateMessage)"
        fi

        if [ "$self_update_helper_container_started" == true ]; then
            Write-Log "INFO" "<print_line_top>"
            Write-Log "INFO" "║ SELF-UPDATE INITIATION"
            Write-Log "INFO" "<print_line_top>"
            Write-Log "INFO" "    Setting update status flag in \"$self_update_helper_container_name:/opt/dcu/.main_update_process_completed\"..."
            { $cmd_docker exec $self_update_helper_container_name /bin/bash -c 'echo "true" > /opt/dcu/.main_update_process_completed' > /dev/null; result=$?; } || result=$?
            [ $result -eq 0 ] && Write-Log "DEBUG" "      => Succeeded"
            [ $result -ne 0 ] && Write-Log "ERROR" "      => Failed: $result"
        fi
    else
        Write-Log "INFO"  "<print_line_top>"
        Write-Log "INFO"  "║  PROCESSING CONTAINERS"
        Write-Log "INFO"  "<print_line_btn>"
        Write-Log "ERROR" "    No containers found by running command \"$cmd_docker ps -q $1\""
    fi
}

Parse-Arguments() {
    local arguments_passed=false && [[ $# -gt 0 ]] && arguments_passed=true

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|\/help|-\?|\/\?)
                echo ""
                echo "Usage: dcu [ [--dry-run|--run] [--filter name|id=VALUE] [--force] ] [--help] [--version]"
                echo "Options:"
                echo "  --dry-run    -dr        Run DCU in dry-run mode (this temporarily enforces test mode to be enabled)"
                echo "  --force      -f         Force lock acquisition"
                echo "  --help       -?         Display this help"
                echo "  --run        -r         Run DCU (considering the current configuration for test mode)"
                echo "  --version    -v         Display the current version"
                echo "  --debug                 Set log level to debug mode"
                echo ""
                return 0
                ;;
            --version|\/version|-v|\/v)
                echo "$(Get-ScriptVersion)"
                return 0
                ;;
            --debug)
                logLevel="DEBUG"
                shift
                ;;
            --dry-run|\/dry-run|-dr|\/dr)
                param_dry_run=true
                test_mode=true

                if [[ "$2" == "--help" ]] || [[ "$2" == "/help" ]] || [[ "$2" == "-?" ]] || [[ "$2" == "/?" ]]; then
                    echo ""
                    echo "Options:"
                    echo "  --debug                 Set log level to debug mode"
                    echo "  --filter                Filter processed containers by the following conditions:"
                    echo "                            name=My_Container_Name"
                    echo "                            id=My_Container_ID"
                    echo "  --force                 Force lock acquisition"
                    echo ""
                    return 0
                fi

                shift
                ;;
            --run|\/run|-r|\/r)
                param_run=true

                if [[ "$2" == "--help" ]] || [[ "$2" == "/help" ]] || [[ "$2" == "-?" ]] || [[ "$2" == "/?" ]]; then
                    echo ""
                    echo "Options:"
                    echo "  --debug                 Set log level to debug mode"
                    echo "  --filter                Filter processed containers by the following conditions:"
                    echo "                            name=My_Container_Name"
                    echo "                            id=My_Container_ID"
                    echo "  --force                 Force lock acquisition"
                    echo ""
                    return 0
                fi

                shift
                ;;
            --force|\/force|-f|\/f)
                param_force=true
                shift
                ;;
            --filter)
                if [[ "$2" =~ ^(name|id)=[a-zA-Z0-9_-]+$ ]]; then
                    docker_ps_filter="--filter $2"
                    shift 2
                elif [[ "$2" == "--help" ]] || [[ "$2" == "/help" ]] || [[ "$2" == "-?" ]] || [[ "$2" == "/?" ]]; then
                    echo ""
                    echo "Options:"
                    echo "  --filter                Filter processed containers by the following conditions:"
                    echo "                            name=My_Container_Name"
                    echo "                            id=My_Container_ID"
                    echo ""
                    return 0
                else
                    echo "[$(date +%Y/%m/%d\ %H:%M:%S)] ERROR   Argument parsing error: Invalid filter. Use --filter name|id=VALUE"
                    return 1
                fi
                ;;
            *)
                echo "[$(date +%Y/%m/%d\ %H:%M:%S)] ERROR   Argument parsing error: Unknown parameter passed: \"$1\""
                return 1
                ;;
        esac
    done

    if [ $param_dry_run ] || [ $param_run ] || [ $arguments_passed == false ]; then
        Write-Log "INFO"  "<print_line_top>"
        Write-Log "INFO"  "║  INITIALIZING"
        Write-Log "INFO"  "<print_line_btn>"
    fi

    if [ $param_force ]; then
        Write-Log "INFO" "    Removing PID file (\"$pidFile\")"
        rm -f "$pidFile" 2>/dev/null || Write-Log "ERROR" "      Failed to remove PID file (\"$pidFile\")"
    fi

    Acquire-Lock
    Validate-ConfigFile
    Test-Prerequisites
    [ -z $test_mode ] && test_mode=$(Read-INI "$configFile" "general" "test_mode")
    [ -z $logLevel ]  && logLevel=$(Read-INI "$configFile" "log" "level" | tr '[:lower:]' '[:upper:]')
    Main "$docker_ps_filter"
    End-Script
}

Parse-Arguments "$@"
