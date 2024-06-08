# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.11.9


# Build stage 1:
# - Build the tracer extension.
FROM --platform=linux/amd64 python:${PYTHON_VERSION}-slim

RUN rm -f /etc/apt/apt.conf.d/docker-clean
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
    apt -o Acquire::Check-Valid-Until=false update && \
    apt install -y --no-install-recommends build-essential

RUN mkdir /source/
RUN mkdir /build/

COPY extensions/ /source/extensions/

WORKDIR /source/extensions/

# By using the name 'build_docker', we make sure that we don't
# use already-compiled files that might be copied from the host.
RUN [ "/usr/local/bin/python3", "setup.py", "build_ext", "--build-lib", "build_docker" ]

WORKDIR /

# We want only this single file from the extensions/build_docker/ directory.
RUN cp /source/extensions/build_docker/tracer.cpython-3*-x86_64-linux-gnu.so /build/




# The actual image
FROM --platform=linux/amd64 python:${PYTHON_VERSION}-slim

# This will contain the files as if it's the root of the
# project. By keeping this order, we make sure that the
# codes can be run both inside and outside Docker.
RUN mkdir /main/
WORKDIR /main/

RUN mkdir simulator/
RUN mkdir simulator/extensions/

# To be compatible with the 'import' statement in the
# entry.py script, that might be executed outside of
# Docker with directly-build extensions.
COPY --from=0 /build/ simulator/extensions/build/

COPY requirements.txt .
RUN [ "/usr/local/bin/python3", "-m", "pip", "install", "-r", "requirements.txt" ]

COPY entry.py simulator/
COPY daemon.py simulator/
COPY settings.py simulator/

COPY --from=project_root common/ common/
COPY --from=project_root games/ games/

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# TODO: Currently we're letting an script (daemon.py) handle spawning
# the workers. It would be better if we used the 'replicas' option
# that docker provides; however, since we want each worker to grab
# its previous messages from the redis stream in case it crashes, we
# must give it a persistent name, for which we index each worker in
# a sequential manner; but, it's not normally possible to let each
# container know its index among the replicas (e.g., as an env var),
# so we're stuck with this method. Of course, it could be better if
# we get around this in some better way (e.g., XPENDING or XAUTOCLAIM
# in redis), but they have their own problems (e.g., we don't know
# how long a simulation will continue, so we can't tell when we should
# claim unacked messages of other workers.). Think about this and fix
# it later in a more efficient way.
ENTRYPOINT [ "/usr/local/bin/python3", "-m", "simulator.daemon" ]
