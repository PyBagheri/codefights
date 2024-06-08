# This file is used to set simulator settings.

# *********************************************************
# It's recommended that you DO NOT INCLUDE SENSITIVE
# INFORMATION IN THIS FILE, AS IT WILL ALSO BE ACCESSED
# BY THE CODERUNNER. But, you can adjust coderunner/build.py
# to determine which settings will be accessed by the
# coderunner; HOWEVER, note that we use pickle for that,
# which might implicitly include other objects too (like
# class objects). So, be mindful.
# *********************************************************

import signal
from pathlib import Path


SIMULATOR_ROOT = Path(__file__).parent


# This is only used for reference within this file.
# Fill this if you need more syscalls.
_SYSCALLS_NUMBERS = {
    'mmap': 9,
    'munmap': 11,
    'brk': 12
}


# We set max write size considerably less than the
# pipe size for each coderunner child's pipe's size.
# This is so that the child cannot write bytes anywhere
# close to the size of the pipe, and thus it won't be
# put into a hang for it (kernel waits for other ends
# to read from the pipe, which we don't expect, and
# thus the process would remain in sleep and we couldn't
# finish the simulation).
CHILD_MAX_WRITE_SIZE = 2048
CHILD_PIPE_SIZE = 4096


# We keep these numbers fixed for convenience.
# The names that start with an underline are for those
# fd's that are used by this worker/tracer, and the
# ones without an underline are for the coderunner side
# (forkserver or forked child).
#
# NOTE: Even though we've made sure that even if the fd numbers
# for the forkserver and the forked children are the same, there
# would be no conflict; but still, we better of choose different
# numbers (it wouldn't hurt).
#
# NOTE: These numbers MUST be high enough that we would be sure
# that the forkserver or the forked children would not make any
# fd with these numbers before we dup2() them (e.g., when creating
# the pipes). This is because we don't have checks for this yet.
FORKSERVER_PIPES_FDS = {'r': 20, '_w': 21, '_r': 22, 'w': 23}
FORKED_PIPES_FDS = {'r': 30, '_w': 31, '_r': 32, 'w': 33}


##################################################################
# Modify this if you need to change the allowed syscalls.
##################################################################
#
# WARNING: Besides the fact that the allowed syscalls must be quite
# limited, we explicitly emphasize that the following syscall families
# MUST NOT be allowed:
#
#   1) Anything related to exiting and closing the process. The forked
#      children are not allowed to exit on their own, and we kill them
#      once we're done with them.
#
#   2) MUST NOT include the read() or the write() syscalls. They are
#      handled specifically and with special supervision. They are only
#      used for communication. They ARE NOT allowed to be called by the
#      player code (even though they can do it by some easy hacks, but
#      if they do it wrongly, they'd be eliminated).
_ALLOWED_SYSCALLS = (
    'mmap',
    'munmap',
    'brk'
)


##################################################################
# DO NOT CHANGE THIS DIRECTLY; CHANGE '_ALLOWED_SYSCALLS' INSTEAD.
##################################################################
#
# Note that this MUST NOT contain the read() or the write() syscalls.
# PTRACE_ALLOWED_SYSCALLS = tuple(_SYSCALLS_NUMBERS[sn] for sn in _ALLOWED_SYSCALLS)
PTRACE_ALLOWED_SYSCALLS = tuple(_SYSCALLS_NUMBERS[sn] for sn in _ALLOWED_SYSCALLS)


##################################################################
# DO NOT CHANGE THIS DIRECTLY; CHANGE '_ALLOWED_SYSCALLS' INSTEAD.
##################################################################
#
# WARNING: These syscalls are passed to seccomp. In order to
# prevent read() and write() from being executed wrongly, we
# MUST have the tracer tracing the child do it for us. Seccomp
# is here just for more security.
#
# WARNING: read() and write() aren't actually allowed to be run
# by the player. The only reason we're including them here is for
# control and communication purposes with the coderunner. They
# are used for 1) sending commands and receiving responses, and
# 2) signaling back and forth with the worker.
SECCOMP_ALLOWED_SYSCALLS = _ALLOWED_SYSCALLS + ('read', 'write')



# Used for waitpid()s in this file.
# The same as __WALL.
WAITPID_FLAGS = 0x40000000


GAME_CLASSES_RELOAD_SIGNAL = signal.SIGUSR1

CPU_TIME_EXCEED_SIGNAL = signal.SIGUSR1


# The index.py module inside the games root package. The
# games package must be a either a docker volume in a
# container or the games root package on the host machine.
# This is relative to the parent of the simulator root
# (the entry will be run using "python -m simulator.entry").
# For this matter, the docker volume for games root package
# must be mounted in the correct path.
GAMES_INDEX_MODULE = 'games.index'


# -------- Control codes --------

# We're not using a class to organize these
# names, to rule out the possible "hidden" ways
# to access the module-level stuff through the
# class. This is just added security, NOT reliable
# on its own.

# Used in the fork server.
CC_F_FORK_CHILD = 'f'  # MUST NOT be a number string
CC_F_CONTINUE = '0'

# Used in the children.
CC_C_CHILD_READY = '3'
CC_C_START_SIMULATION = '4'

# -------------------------------
