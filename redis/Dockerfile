FROM redis:7.2.5

ARG PRODUCTION_UID
ARG PRODUCTION_GID


# In production, we must avoid running service containers as
# root. Plus, in case of bind mounts, it's necessary that the
# owner UID and optionally the GID of those mounted files
# matches that of the user that runs the service and its primary
# group, so that it can have access to those files without having
# to allow read and/or write for all users so that different users
# can access it (e.g., chmod o+rw); we'd like to keep the permissions
# as they are. Therefore the best solution (as is also a common
# practice) is to have users and groups with matching UID's and
# optionally GID's on the host and the container, and chown the
# files from the host (using root permissions) to be owned by that
# user and/or group. This way, both the container and the host can
# access it with the same permissions. For more info, see the links
# below. IMHO, to avoid confusion and further problems, it's best
# to make the group ID's match too; I'm not sure if it would have
# any security implications otherwise or not (search later).
#
# Also note that it's only the UID and GID numbers that matter
# for the shared files between the container and the host; names
# are only a local identifier. These numbers must be specified
# as build args upon build, and don't forget to make the user
# with the same UID and GID on the host.
#
# In development, we currently run service containers with root.
# In order to have non-root users for development too, see the
# links below.
#
# More info:
# - https://stackoverflow.com/questions/71918710 (both answers)
# - https://stackoverflow.com/a/54787364
# As suggested in the second link, we're creating the user for
# production in the image build stage. If no group ID is specified,
# then we use the user's default group.

RUN <<EOR
    if [ -n "${PRODUCTION_UID}" ]; then
        useradd -o -m -u "${PRODUCTION_UID}" app

        PRODUCTION_GID=${PRODUCTION_GID:-${PRODUCTION_UID}}
        if [ "${PRODUCTION_GID}" -ne "${PRODUCTION_UID}" ]; then
            groupadd -g "${PRODUCTION_GID}" app
        fi

        mkdir -p /var/run/redis/
        chown -R ${PRODUCTION_UID}:${PRODUCTION_GID} /var/run/redis/
    fi
EOR


# Make sure to sync the redis unix socket location in the global config files.
# NOTE: Even through docker can take care of the logs by letting them be printed
# on the stdout, I'd currently want to have them as files on the host instead,
# by a bind mount to the path specified below.
ENTRYPOINT [ "redis-server", "--unixsocket", "/var/run/redis/redis.sock", "--unixsocketperm", "775", "--logfile", "/var/log/redis/redis-server.log" ]
