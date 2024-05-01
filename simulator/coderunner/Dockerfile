# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.11.9

# Build stage 1:
# - Compile the run.py to get rid of the comments.
# - Build the settings to only include the necessary settings
#   and also get rid of the comments.
FROM --platform=linux/amd64 python:${PYTHON_VERSION}-slim

RUN mkdir /source/
RUN mkdir /build/

COPY run.py /source/
COPY --from=simulator_dir settings.py /source/
COPY --from=simulator_dir extensions/build/tracee.cpython-3*-x86_64-linux-gnu.so /build/
COPY build.py /source/

RUN [ "/usr/local/bin/python3", "/source/build.py" ]


# Build stage 2: The actual image
FROM --platform=linux/amd64 python:${PYTHON_VERSION}-slim

RUN mkdir /coderunner/

COPY --from=0 /build/* /coderunner/

ENTRYPOINT [ "/usr/local/bin/python3", "/coderunner/run.pyc" ]

# The coderunner MUST be run as a specified user with
# limitied permissions, dedicated for the coderunner.
# We get rid of the default "root" here. Upon running,
# we should run as the specified user.
USER nobody
