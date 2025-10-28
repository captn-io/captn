#!/bin/bash
# Nextcloud-specific Post-Update Script
# This script is executed after container updates

set -e

CONTAINER_DATA_BASE_DIR="/var/opt/JK.NET/data/docker"

echo "=== Post-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Log Level: $CAPTN_LOG_LEVEL"
echo "Config Dir: $CAPTN_CONFIG_DIR"
echo "Scripts Dir: $CAPTN_SCRIPTS_DIR"
echo "Data Base Dir: $CONTAINER_DATA_BASE_DIR"
echo "Timestamp: $(date)"

if [ "$CAPTN_DRY_RUN" = "false" ]; then
    if docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
        echo "Container $CAPTN_CONTAINER_NAME is running, proceeding..."
    else
        echo "Container $CAPTN_CONTAINER_NAME is not running. Exiting."
        exit 1
    fi

    echo "Turning on Maintenance Mode for $CAPTN_CONTAINER_NAME..."
    docker exec -u www-data $CAPTN_CONTAINER_NAME php console.php maintenance:mode --on || true

    # Check if maintenance mode is on by polling the URL
    URL="https://cloud.jk-net.com/"
    TIMEOUT=300   # max wait time in seconds
    INTERVAL=5    # interval between checks in seconds
    ELAPSED=0

    echo "Waiting for maintenance mode to be enabled..."

    while true; do
        # Use curl to check HTTP status code
        HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "$URL")

        # Typically maintenance mode returns 503 or similar, normal mode 200
        if [ "$HTTP_STATUS" -eq 503 ]; then
            echo "Maintenance mode is enabled"
            break
        fi

        # Timeout check
        if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
            echo "Timeout reached after $TIMEOUT seconds"
            exit 1
        fi

        sleep "$INTERVAL"
        ELAPSED=$((ELAPSED + INTERVAL))
    done

    # Add missing indices
    echo "Nextcloud DB: Adding missing indices..."
    docker exec -u www-data $CAPTN_CONTAINER_NAME php console.php db:add-missing-indices

    # Customizing default folder structure
    echo "Removing default folders and files..."
    rm -Rf $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/*

    echo "Creating custom folders..."
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Bilder\ \&\ Videos/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Bilder\ \&\ Videos/Feste\ \&\ Veranstaltungen/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Bilder\ \&\ Videos/Kamera\ Uploads/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Bilder\ \&\ Videos/Sonstige/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Bilder\ \&\ Videos/Unternehmungen/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Bilder\ \&\ Videos/Urlaub/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Dokumente/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Dokumente/Gescannte\ Dokumente/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Dokumente/Rechnungen\ \&\ Belege/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Dokumente/Sonstige\ Dokumente/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Sonstige\ Dateien/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Sonstige\ Dateien/Contacts/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Sonstige\ Dateien/Desktop/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Sonstige\ Dateien/Downloads/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Sonstige\ Dateien/Favorites/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Sonstige\ Dateien/Links/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Sonstige\ Dateien/Music/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Sonstige\ Dateien/Searches/
    mkdir $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Eigene\ Dateien/Sonstige\ Dateien/Videos/

    echo "Creating custom Readme.md for new users..."
    echo '# Willkommen bei JK.NET! 📱 ☁️ 💻' > $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Readme.md
    echo '' >> $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Readme.md
    echo 'Dies ist ein sicherer Ort für all deine Dateien. Für einen schnelleren Zugriff, [lade](https://nextcloud.com/install/) dir die Nextcloud Apps auf deine Geräte herunter.' >> $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/Readme.md

    echo "Setting permissions for skeleton directory..."
    chown -Rf 33 $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/
    find $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/ -type d -exec chmod 755 {} \;
    find $CONTAINER_DATA_BASE_DIR/$CAPTN_CONTAINER_NAME/appdata/config/core/skeleton/ -type f -exec chmod 644 {} \;

    # Updating repositories
    docker exec $CAPTN_CONTAINER_NAME apt -y update
    docker exec $CAPTN_CONTAINER_NAME apt -y upgrade

    # Installing apt-utils
    docker exec $CAPTN_CONTAINER_NAME apt -y install apt-utils

    # Installing cron and add Nextcloud cron jobs (outdated)
    # echo "Installing cron within $CAPTN_CONTAINER_NAME container and adding cron jobs..."
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt -y --no-install-recommends install crond || true'
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'service cron start'
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'echo "*/5 * * * * /usr/local/bin/php -f /var/www/html/cron.php" > /tmp/crontab'
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'echo "0   6 * * * /usr/local/bin/php -f /var/www/html/occ app:update --all" >> /tmp/crontab'
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'crontab -u www-data /tmp/crontab'
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'rm -f /tmp/crontab'
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c "sed -i '3i\ \' /entrypoint.sh"
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c "sed -i '3i\service cron start\' /entrypoint.sh"
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c "sed -i '3i\# Start cron service\' /entrypoint.sh"
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c "sed -i '3i\ \' /entrypoint.sh"

    # Configuring BusyBox cron inside container (not working) -> Need to realize this via host's crontab
    # echo "Configuring BusyBox cron for $CAPTN_CONTAINER_NAME..."

    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'rm -rf /etc/crontabs /var/log/cron'
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'mkdir -p /etc/crontabs /var/log/cron'

    # Create log files with appropriate permissions
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'touch /var/log/cron/occ_update.log /var/log/cron/cron_php.log'
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'chmod 666 /var/log/cron/occ_update.log /var/log/cron/cron_php.log'

    # Create www-data crontab
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'echo "*/5 * * * * /usr/local/bin/php -f /var/www/html/cron.php >> /var/log/cron/cron_php.log 2>&1" > /etc/crontabs/www-data'
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'echo "0 6 * * * /usr/local/bin/php -f /var/www/html/occ app:update --all >> /var/log/cron/occ_update.log 2>&1" >> /etc/crontabs/www-data'

    # Set ownership and permissions
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'chown www-data:www-data /etc/crontabs/www-data'
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'chmod 600 /etc/crontabs/www-data'

    # Ensure BusyBox cron starts when container runs
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c "sed -i '3i\# Start BusyBox cron service' /entrypoint.sh"
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c "sed -i '4i\busybox crond -f -L /var/log/cron/cron.log &' /entrypoint.sh"


    # Remove systemd and related packages
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt-get remove --purge -y systemd systemd-sysv libpam-systemd libnss-systemd dbus dbus-user-session dbus-system-bus-common'

    # Installing preview generator extensions
    echo "Updating and installing preview generator extensions..."
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt -y --no-install-recommends install ffmpeg imagemagick ghostscript'

    # Installing pdftk
    echo "Installing pdftk..."
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt -y --no-install-recommends install pdftk'

    # Installing Workflow OCR extensions
    echo "Installing OCR extensions..."
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt -y --no-install-recommends install ocrmypdf'

    echo "Installing English OCR language..."
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt -y --no-install-recommends install tesseract-ocr-eng'

    echo "Installing German OCR language..."
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt -y --no-install-recommends install tesseract-ocr-deu'

    echo "Installing Spanish OCR language..."
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt -y --no-install-recommends install tesseract-ocr-spa'

    # Installing extract extensions
    echo "Installing extract extensions..."
    #docker exec $CAPTN_CONTAINER_NAME apt -y install unrar-free
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt -y --no-install-recommends install p7zip'
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt -y --no-install-recommends install p7zip-full'

    # Install Rar
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt -y --no-install-recommends install wget'
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'wget http://ftp.us.debian.org/debian/pool/non-free/r/rar/rar_7.12-1_amd64.deb'
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'dpkg -i rar_7.12-1_amd64.deb'
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt-get --no-install-recommends install -f -y'

    # Install Unrar ()
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'wget http://ftp.us.debian.org/debian/pool/non-free/u/unrar-nonfree/unrar_7.1.10-3_amd64.deb'
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'dpkg -i unrar_7.1.10-3_amd64.deb'
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt-get --no-install-recommends install -f -y'

    # Installing bz2 extension
    # echo "Installing bz2 extension..."
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt -y --no-install-recommends install libbz2-dev'
    # docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'docker-php-ext-install bz2'

    # Pushing OnlyOffice secret to Nextcloud database if OnlyOffice is installed
    # if docker ps -a --filter "name=OnlyOffice" | grep -q OnlyOffice; then
    #     echo "OnlyOffice detected. Configuring MariaDB with OnlyOffice secret..."
    #     docker exec MariaDB sh -c 'rm ~/.my.cnf' || true
    #     docker exec MariaDB sh -c 'echo "[mysql]" >> ~/.my.cnf'
    #     docker exec MariaDB sh -c 'echo "user = root" >> ~/.my.cnf'
    #     docker exec MariaDB sh -c 'echo "password = admin" >> ~/.my.cnf'
    #     docker exec MariaDB sh -c 'echo "" >> ~/.my.cnf'
    #     docker exec MariaDB sh -c 'echo "[mysqldump]" >> ~/.my.cnf'
    #     docker exec MariaDB sh -c 'echo "user = root" >> ~/.my.cnf'
    #     docker exec MariaDB sh -c 'echo "password = admin" >> ~/.my.cnf'
    #     jwt_secret=$(docker exec OnlyOffice grep -A2 "secret" /etc/onlyoffice/documentserver/local.json | grep "string" | sed 's/^.\{21\}//' | sed 's/.$//') && docker exec MariaDB mariadb -u root -e "USE $CAPTN_CONTAINER_NAME; UPDATE oc_appconfig SET configvalue='${jwt_secret}' WHERE appid='onlyoffice' AND configkey='jwt_secret';"
    #     docker exec MariaDB sh -c 'rm ~/.my.cnf' || true
    # fi

    # Installing LibreOffice for automated PDF conversion
    echo "Installing LibreOffice for automated PDF conversion capabilities..."
    docker exec $CAPTN_CONTAINER_NAME /bin/bash -c 'apt -y --no-install-recommends install libreoffice'

    echo "Turning off Maintenance Mode for $CAPTN_CONTAINER_NAME..."
    docker exec -u www-data $CAPTN_CONTAINER_NAME php console.php maintenance:mode --off

    # Check if maintenance mode is off by polling the URL
    URL="https://cloud.jk-net.com/"
    TIMEOUT=300   # max wait time in seconds
    INTERVAL=5    # interval between checks in seconds
    ELAPSED=0

    echo "Waiting for maintenance mode to be disabled..."

    while true; do
        # Use curl to check HTTP status code
        HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "$URL")

        # Typically maintenance mode returns 503 or similar, normal mode 200, or 302
        if [[ "$HTTP_STATUS" -eq 200 || "$HTTP_STATUS" -eq 302 ]]; then
            echo "Maintenance mode is disabled"
            break
        fi

        # Timeout check
        if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
            echo "Timeout reached after $TIMEOUT seconds"
            exit 1
        fi

        sleep "$INTERVAL"
        ELAPSED=$((ELAPSED + INTERVAL))
    done

    echo "Upgrading $CAPTN_CONTAINER_NAME..."
    docker exec -u www-data $CAPTN_CONTAINER_NAME php occ upgrade

    echo "Restarting container $CAPTN_CONTAINER_NAME..."
    docker restart $CAPTN_CONTAINER_NAME

else
    echo "Would process post-update tasks"
fi

echo "=== Post-Update Script Completed ==="
exit 0