import os
import sys
import importlib
import subprocess
import signal
import atexit
from pathlib import Path

# The config file can be either inside the docker container
# as a docker config, or out of docker in the project root.
# This is so that we can run this both with and without docker.
os.environ.setdefault('GLOBAL_CONFIG_MODULE', 'config')

global_config = importlib.import_module(os.environ.get('GLOBAL_CONFIG_MODULE'))


WORKER_NAME_FORMAT = global_config.WORKER_NAME_FORMATS['result_processor']

BASE_DIR = Path(__file__).parent.parent


workers = []


@atexit.register
def end_all(*args, **kwargs):
    for w in workers:
        w.kill()  # will not error even if already dead


# If one worker dies, kill all of them. Basically
# there should be no occasion when a worker exits
# on its own. If so, that's a serious bug.
signal.signal(signal.SIGCHLD, end_all)


if __name__ == '__main__':
    for i in range(global_config.WORKERS['result_processor']):
        worker_name = WORKER_NAME_FORMAT.format(i)
        
        workers.append(subprocess.Popen(
            [
                sys.executable,
                '-m',
                'result_processor.entry',
                worker_name
            ],
            
            # So that we can run the entry.py script through its parent
            # directory name. This way the modules in this level will
            # also be accessible for import to the script.
            cwd=BASE_DIR
        ))


# Exit with literally any signal.
signal.pause()
