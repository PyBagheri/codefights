# This file is only meant for DEBUGGING & DEVELOPMENT.
#
# The names, paths, URLs, ports and keys used here may
# or may not make their way to the production.


DEBUG = True


ALLOWED_HOSTS = []


CSRF_TRUSTED_ORIGINS = ['http://localhost:8001']


# Relative to the website's main domain.
ADMIN_URL = 'admin/'


POSTGRES = {
    'DATABASE_NAME': 'codefights',
    'USER': 'postgres',
    'HOST': '127.0.0.1',
    'PORT': '5432'
}


STATIC_URL = 'static/'

STATIC_ROOT = 'staticfiles/'



MEDIA_URL = 'files/'

# It's recommended to be somewhere in /srv. See:
# https://unix.stackexchange.com/questions/233343/
MEDIA_ROOT = '/srv/codefights/'


# These are relative to the MEDIA_ROOT.
FIGHT_CODES_DIR = 'fights/'
PRESET_CODES_DIR = 'presets/'
TEMPLATE_CODES_DIR = 'templates/'


DEFAULT_FROM_EMAIL = 'test@dev.com'



LOGGING_ROOT = '/tmp/testlogdir'

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
    'DOCKER_IMAGE': '0b6348f2e7c4a',
    
    # AppArmor profile for the coderunner container. Note that
    # this only applies to the files inside the container.
    'DOCKER_APPARMOR_PROFILE': 'cr-container-profile'
}
