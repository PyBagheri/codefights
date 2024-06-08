# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.11.9


FROM --platform=linux/amd64 python:${PYTHON_VERSION}-slim AS web

# ncat (nc) is used for health-checking.
# The rest of the packages are required for the psycopg2,
# as it will actually compile things from the source (note
# that we didn't use psycopg2-binary, which, as per the
# manual, isn't recommended for production).
RUN rm -f /etc/apt/apt.conf.d/docker-clean
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
    apt -o Acquire::Check-Valid-Until=false update && \
    apt install -y --no-install-recommends gcc linux-libc-dev musl-dev libpq-dev libc6-dev ncat


# This will contain the files as if it's the root of the
# project. By keeping this order, we make sure that the
# codes can be run both inside and outside Docker.
RUN mkdir /main/
WORKDIR /main/

COPY requirements.txt .

RUN [ "/usr/local/bin/python3", "-m", "pip", "install", "-r", "requirements.txt" ]


# The Django apps
COPY gamespecs/ gamespecs/
COPY fights/ fights/
COPY accounts/ accounts/
COPY pages/ pages/

# The other parts
COPY common/ common/
COPY utils/ utils/
COPY django_project/ django_project/
COPY games/ games/
COPY templates/ templates/
COPY manage.py manage.py

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# We'll keep the port number 8000 as a fixed number.
ENTRYPOINT [ "gunicorn", "django_project.wsgi:application", "--bind", "0.0.0.0:8000" ]





FROM web AS result_processor

# The result processor
COPY result_processor/ result_processor/

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
ENTRYPOINT [ "/usr/local/bin/python3", "-m", "result_processor.daemon" ]
