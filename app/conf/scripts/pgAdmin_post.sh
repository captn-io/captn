#!/bin/bash
# pgAdmin-specific Post-Update Script
# This script is executed after container updates

set -e

echo "=== Post-Update Script Started ==="
echo "Container: $CAPTN_CONTAINER_NAME"
echo "Script Type: $CAPTN_SCRIPT_TYPE"
echo "Dry Run: $CAPTN_DRY_RUN"
echo "Log Level: $CAPTN_LOG_LEVEL"
echo "Config Dir: $CAPTN_CONFIG_DIR"
echo "Scripts Dir: $CAPTN_SCRIPTS_DIR"
echo "Timestamp: $(date)"

if [ "$CAPTN_DRY_RUN" = "false" ]; then
    if docker ps --format "{{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
        echo "Container $CAPTN_CONTAINER_NAME is running, proceeding..."
    else
        echo "Container $CAPTN_CONTAINER_NAME is not running. Exiting."
        exit 1
    fi

    # Wait a bit for the container to be fully ready
    echo "Waiting 10 seconds..."
    sleep 10

    # Configuration for authelia auth
    echo "Writing authentication configuration to /pgadmin4/config_local.py"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"AUTHENTICATION_SOURCES = ['oauth2']\" > /pgadmin4/config_local.py"

    echo "Enabling auto user creation"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"OAUTH2_AUTO_CREATE_USER = True\" >> /pgadmin4/config_local.py"

    echo "Starting OAuth2 configuration block"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"OAUTH2_CONFIG = [{\" >> /pgadmin4/config_local.py"

    echo "Setting OAuth2 provider details"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"    'OAUTH2_NAME': 'authentik',\" >> /pgadmin4/config_local.py"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"    'OAUTH2_DISPLAY_NAME': 'authentik',\" >> /pgadmin4/config_local.py"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"    'OAUTH2_CLIENT_ID': 'H1xPAMgUF0vj31U4xGQ4SGaqpotRdogmMuoPv3XZ',\" >> /pgadmin4/config_local.py"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"    'OAUTH2_CLIENT_SECRET': 'bfIMLeEyb4hAzGi3wuFW0qIEPsz2uQFjsbrwThp62dN9fsgBcVjFQfpaDspaQXc6QvBzlQJODidUcJu8KxkIIDAT1lp4xxlY1OICqmy1Zmmi7Iaehu6ph6DajrbUibTa',\" >> /pgadmin4/config_local.py"

    echo "Defining OAuth2 endpoints"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"    'OAUTH2_API_BASE_URL': 'https://auth2.jk-net.com',\" >> /pgadmin4/config_local.py"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"    'OAUTH2_AUTHORIZATION_URL': 'https://auth2.jk-net.com/application/o/authorize/',\" >> /pgadmin4/config_local.py"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"    'OAUTH2_TOKEN_URL': 'https://auth2.jk-net.com/application/o/token/',\" >> /pgadmin4/config_local.py"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"    'OAUTH2_USERINFO_ENDPOINT': 'https://auth2.jk-net.com/application/o/userinfo/',\" >> /pgadmin4/config_local.py"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"    'OAUTH2_SERVER_METADATA_URL': 'https://auth2.jk-net.com/application/o/pg-admin/.well-known/openid-configuration',\" >> /pgadmin4/config_local.py"

    echo "Setting OAuth2 scope and user claim"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"    'OAUTH2_SCOPE': 'openid email profile',\" >> /pgadmin4/config_local.py"

    echo "Defining OAuth2 UI settings"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"    'OAUTH2_ICON': 'fa-key',\" >> /pgadmin4/config_local.py"

    echo "Closing OAuth2 configuration block"
    docker exec -u root $CAPTN_CONTAINER_NAME sh -c "echo \"}]\" >> /pgadmin4/config_local.py"

    # Configuration for ldap auth
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c "echo \"AUTHENTICATION_SOURCES = ['ldap', 'internal']\" > /pgadmin4/config_local.py"
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c "echo \"LDAP_AUTO_CREATE_USER = True\" >> /pgadmin4/config_local.py"
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c "echo \"LDAP_CONNECTION_TIMEOUT = 30\" >> /pgadmin4/config_local.py"
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c "echo \"LDAP_SERVER_URI = 'ldap://lldap:389'\" >> /pgadmin4/config_local.py"
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c "echo \"LDAP_USERNAME_ATTRIBUTE = 'uid'\" >> /pgadmin4/config_local.py"
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c "echo \"LDAP_BIND_USER = 'cn=jk.net_admin,dc=jk-net,dc=com'\" >> /pgadmin4/config_local.py"
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c 'password="3x^yQj4O0W7wXmk*2^@EByr@"; echo "LDAP_BIND_PASSWORD = '\''$password'\''" >> /pgadmin4/config_local.py'
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c "echo \"LDAP_BASE_DN = 'ou=people,dc=jk-net,dc=com'\" >> /pgadmin4/config_local.py"
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c "echo \"LDAP_SEARCH_BASE_DN = 'ou=people,dc=jk-net,dc=com'\" >> /pgadmin4/config_local.py"
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c "echo \"LDAP_SEARCH_FILTER = '(&(|(objectClass=inetOrgPerson))(|(memberOf=cn=PostgreSQL-Administrators,ou=groups,dc=jk-net,dc=com)))'\" >> /pgadmin4/config_local.py"
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c "echo \"X_CONTENT_TYPE_OPTIONS = ''\" >> /pgadmin4/config_distro.py"
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c "echo \"ENHANCED_COOKIE_PROTECTION = False\" >> /pgadmin4/config_distro.py"
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c "echo \"X_XSS_PROTECTION = '0' >> /pgadmin4/config_distro.py"

    # Configuration for default database connection (not working currently)
    #docker exec -i -u root $CAPTN_CONTAINER_NAME sh -c 'config_file="/pgadmin4/config_local.py"; echo -e "SERVERS = {\\n    '\''Servers'\'': {\\n        '\''JK.NET'\'': {\\n            '\''host'\'': '\''192.168.117.247'\'',\\n            '\''port'\'': 5432,\\n            '\''ssl_mode'\'': '\''prefer'\'',\\n            '\''username'\'': '\''root'\'',\\n            '\''password'\'': '\''Innenmin!S7ErSahSpi3l3Mi7tEPo1!t!5chen'\'',\\n            '\''maintenance_db'\'': '\''postgres'\'',\\n            '\''timeout'\'': 10\\n        }\\n    }\\n}" >> "$config_file"'

    echo "Restarting Docker container $CAPTN_CONTAINER_NAME"
    docker restart $CAPTN_CONTAINER_NAME

    # Wait for container to be ready after restart
    echo "Waiting for container to be ready after restart..."
    sleep 15

    # Final check
    if docker ps --format "table {{.Names}}" | grep -q "^${CAPTN_CONTAINER_NAME}$"; then
        echo "Container $CAPTN_CONTAINER_NAME is running after restart"
    else
        echo "Container $CAPTN_CONTAINER_NAME failed to restart!"
        exit 1
    fi

else
    echo "Would process post-update tasks"
fi

echo "=== Post-Update Script Completed ==="
exit 0