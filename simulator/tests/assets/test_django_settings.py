import os
import sys
from pathlib import Path

TEST_ASSETS_DIR = Path(__file__).parent

# We import the django's settings.py directly because
# we want its dir().
from django_project import settings as project_settings



GAMES_PACKAGE = 'simulator.tests.assets.test_games'

SIMULATOR_USERNAME = 'nobody'

REDIS_SIMULATOR_STREAM = 'teststream1'
REDIS_SIMULATOR_GROUP = 'testgroup1'

REDIS_SIMULATION_RESULTS_STREAM = 'testresultstream1'

LOGGING_ROOT = TEST_ASSETS_DIR / 'test_logging_root'



# See https://stackoverflow.com/questions/2447353/getattr-on-a-module
def __getattr__(key):
    if key in globals().keys():
        return globals()[key]
    
    if hasattr(project_settings, key):
        return getattr(project_settings, key)


def __dir__():
    dir1set = {n for n in dir(project_settings) if n.isupper()}
    dir2set = {n for n in globals().keys() if n.isupper()}
    return list(dir1set.union(dir2set))
