# This file is only meant for DEBUGGING & DEVELOPMENT.
#
# The names, paths, URLs, ports and keys used here may
# or may not make their way to the production.


import os
from pathlib import Path

# Some configs may need to be overriden through environment variables.
E = os.environ.get

_BASE_DIR = Path(__file__).parent




######################## CONFIGS BEGIN HERE ########################

DEBUG = True


ALLOWED_HOSTS = []


CSRF_TRUSTED_ORIGINS = ['http://localhost:8000']


# Relative to the website's main domain.
ADMIN_URL = 'admin/'


POSTGRES = {
    'DATABASE_NAME': 'codefights_dev',
    'USER': 'postgres',
    'HOST': E('POSTGRES_HOST', '127.0.0.1'),
    'PORT': '5432'
}


STATIC_URL = E('STATIC_URL', 'static/')

# Unlike the media root, this better be a fixed directory
# in the project's base.
STATIC_ROOT = _BASE_DIR / 'staticfiles/'



MEDIA_URL = E('MEDIA_URL', 'media/')

# It's recommended to be somewhere in /srv. See:
# https://unix.stackexchange.com/questions/233343/
MEDIA_ROOT = Path(E('MEDIA_ROOT', _BASE_DIR / 'media_dev/'))


# These are relative to the MEDIA_ROOT.
FIGHT_CODES_DIR = 'fights/'
PRESET_CODES_DIR = 'presets/'
TEMPLATE_CODES_DIR = 'templates/'


DEFAULT_FROM_EMAIL = 'test@dev.com'

# TODO: Fix for later, so that we can test the email sending.
EMAIL_HOST = ''
EMAIL_PORT = ''
EMAIL_HOST_USER = ''



LOGGING_ROOT = Path(E('LOGGING_ROOT', _BASE_DIR / 'logs_dev'))

LOGGING_FILES_PATHS = {
    'workers': {
        'simulator': 'workers/simulator.log'
    }
}



REDIS_SERVER_URL = 'unix:///var/run/redis/redis.sock'

# Currently we only need only one stream group for these.
REDIS_SIMULATOR_STREAM = 'test_stream_simulator'
REDIS_SIMULATOR_GROUP = 'test_group_simulator'

REDIS_RESULT_PROCESSOR_STREAM = 'test_stream_result_processor'
REDIS_RESULT_PROCESSOR_GROUP = 'test_group_result_processor'



DOCKER_SERVER_URL = 'unix:///var/run/docker.sock'


WORKERS = {
    'simulator': 1,
    'result_processor': 1
}


# Used by spawner daemons.
WORKER_NAME_FORMATS = {
    'simulator': 'simulator_{}',
    'result_processor': 'result_processor_{}',
}


SIMULATOR_CODERUNNER = {
    # The Linux user with minimal previleges that will be used
    # to run the simulations.
    'USERNAME': 'nobody',
    
    # The Docker image's name that was built for the coderunner.
    # See simulator/coderunner.
    'DOCKER_IMAGE': 'codefights_coderunner',
    
    # AppArmor profile for the coderunner container. Note that
    # this only applies to the files inside the container.
    'DOCKER_APPARMOR_PROFILE': 'cr-container-profile'
}
