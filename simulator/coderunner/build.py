import pickle
import py_compile

import settings

INCLUDED_SETTINGS = [
    'CHILD_PIPE_SIZE',
    
    'FORKSERVER_PIPES_FDS',
    'FORKED_PIPES_FDS',
    
    'SECCOMP_ALLOWED_SYSCALLS',
    
    'CPU_TIME_EXCEED_SIGNAL',
    
    # -------- Control codes --------
    
    # Used in the fork server.
    'CC_F_FORK_CHILD',
    'CC_F_CONTINUE',

    # Used in the children.
    'CC_C_CHILD_READY',
    'CC_C_START_SIMULATION',
    
    # -------------------------------
]


_SETTINGS_FILE =  \
"""
import pickle

_settings_dict = pickle.loads({_settings_pickle})

for key, value in _settings_dict.items():
    globals()[key] = value

del key, value
del pickle, _settings_dict
"""


_settings_dict = {}

for s in INCLUDED_SETTINGS:
    _settings_dict[s] = getattr(settings, s)

_settings_pickle = pickle.dumps(_settings_dict)

with open('/source/settings.py', 'w') as f:
    f.write(_SETTINGS_FILE.format(_settings_pickle=_settings_pickle))


py_compile.compile(file='/source/run.py',      cfile='/build/run.pyc')
py_compile.compile(file='/source/settings.py', cfile='/build/settings.pyc')
