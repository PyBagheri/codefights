#!/usr/bin/env bash

# See https://serverfault.com/a/919212
ALLOWED_ENV_VARS='${APP_HOSTNAME} ${SERVER_MAIN_DOMAIN} ${SERVER_FILES_DOMAIN} ${STATIC_ROOT} ${STATIC_URL} ${MEDIA_ROOT} ${MEDIA_URL} ${SSL_CERT_PATH} ${SSL_KEY_PATH} ${ACME_CHALLENGE_ROOT}'
envsubst "$ALLOWED_ENV_VARS" < /etc/nginx/conf.d/nginx.conf.template > /etc/nginx/conf.d/nginx.conf

nginx -g "daemon off;"
