import os
from pathlib import Path
from utils.settings import overrides


TEST_ASSETS_DIR = Path(__file__).parent


LOGGING_ROOT = TEST_ASSETS_DIR / 'logging_root'

REDIS_SIMULATOR_STREAM = 'test_stream_simulator_1'
REDIS_SIMULATOR_GROUP = 'test_group_simulator_1'

REDIS_RESULT_PROCESSOR_STREAM = 'test_stream_result_processor_1'


MEDIA_ROOT = TEST_ASSETS_DIR / 'media_root'


# The test setup must set the environment variable first.
overrides(this=__name__, target=os.environ.get('ORIGINAL_GLOBAL_CONFIG_MODULE'))
