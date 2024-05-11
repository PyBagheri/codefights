import os
import json
import redis
import subprocess
from pathlib import Path
from simulator.tests.assets import test_django_settings as project_settings


SIMULATOR_BASE = Path(__file__).parent.parent


def rm_left_spaces(code, space_count):
    final_lines = []
    
    for l in code.splitlines():
        final_lines.append(l[space_count:])
    
    return '\n'.join(final_lines)


def setUpModule():
    global redis_client, worker
    
    logging_root = project_settings.LOGGING_ROOT
    
    if not logging_root.is_dir():
        logging_root.mkdir(parents=True)
    
    lfp_parent = (logging_root / 
        project_settings.LOGGING_FILES_PATHS['workers']['simulator']
    ).parent
    
    if not lfp_parent.is_dir():
        lfp_parent.mkdir(parents=True)
    
    redis_client = redis.from_url(project_settings.REDIS_SERVER_URL,
                                  decode_responses=True)

    os.environ['DJANGO_SETTINGS_MODULE'] =  \
        'simulator.tests.assets.test_django_settings'
    
    redis_client.delete(
        project_settings.REDIS_SIMULATOR_STREAM,
    )
    
    redis_client.xgroup_create(
        project_settings.REDIS_SIMULATOR_STREAM,
        project_settings.REDIS_SIMULATOR_GROUP,
        mkstream=True
    )
    
    worker = subprocess.Popen([
        str(SIMULATOR_BASE.parent / '.venv/bin/python3'),
        '-m',
        'simulator.entry',
        'testworker1'  # will also be the consumer name
    ])


def tearDownModule():
    global redis_client, worker
    
    del os.environ['DJANGO_SETTINGS_MODULE']
    
    worker.terminate()
    
    redis_client.delete(
        project_settings.REDIS_SIMULATOR_STREAM,
    )
    
    redis_client.delete(
        project_settings.REDIS_SIMULATION_RESULTS_STREAM,
    )
    
    redis_client.close()
    

# A mixin to be included in simulator test cases. It does
# cleanups and setups for redis streams and also provides
# and interface to communicate with the simulator without
# directly dealing with redis.
class SimulatorTests:
    # We include the cleanup on setup too, just
    # to be sure. It doesn't hurt :/
    def setUp(self):
        self.cleanup_redis_streams()
    
    
    def tearDown(self):
        self.cleanup_redis_streams()
    
    
    def cleanup_redis_streams(self):
        redis_client.xtrim(
            project_settings.REDIS_SIMULATOR_STREAM,
            maxlen='0',
        )
        
        redis_client.xtrim(
            project_settings.REDIS_SIMULATION_RESULTS_STREAM,
            maxlen='0',
        )
    
    
    def request_simulation_and_result(self, data):
        redis_client.xadd(project_settings.REDIS_SIMULATOR_STREAM,
            {'data': json.dumps(data)}
        )
        
        # The indices: 1st (and only) stream; 2nd item (messages);
        # 1st (and only) message; 2nd item (message data); the json raw.
        return json.loads(redis_client.xread(
            {project_settings.REDIS_SIMULATION_RESULTS_STREAM: '0'},
            count=1,
            block=0  # block until message arrives
        )[0][1][0][1]['data'])
