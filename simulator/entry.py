import os
import sys

# This module is not meant to be imported.
if __name__ != '__main__':
    exit(1)

# This script must be run as root.
if os.getuid() != 0:
    exit(1)

# The script must be given only one argument: the worker
# name. It's used as the Redis consumer name, as well as
# for logging.
if len(sys.argv) != 2:
    exit(1)
    
WORKER_NAME = sys.argv[1]


import redis
import resource
import signal
import docker
import pwd
import logging
import logging.handlers
from pathlib import Path
import importlib
import functools
import json
from json.decoder import JSONDecodeError
from common.values import TerminationReasons

# The C extension for managing the tracer.
from simulator.extensions.build import tracer

from simulator.extensions.build.tracer import (
    ForkServer_UnknownKill,
    ForkServer_UnknownSignal,
    ForkServer_UnexpectedCont,
    Forked_IllegalSyscall,
    Forked_ENOMEM,
    Forked_UnknownKill,
    Forked_UnknownSignal,
    Forked_UnexpectedCont
)

# This is for when the coderunner child has been
# sabotaged by the player in such a way that it
# does not act in the way we wrote its code. One
# example of this is when we return a 'ready'
# message from the coderunner to announce that the
# initial code has been executed successfully.
# We didn't put this in the tracer module, as it's
# not supposed to be detected by the tracer.
class Forked_CodeSabotage(Exception):
    pass


SIMULATOR_ROOT = Path(__file__).parent


# The config file can be either inside the docker container
# as a docker config, or out of docker in the project root.
# This is so that we can run this both with and without docker.
os.environ.setdefault('GLOBAL_CONFIG_MODULE', 'config')

os.environ.setdefault('SIMULATOR_SETTINGS_MODULE', 'simulator.settings')


settings = importlib.import_module(os.environ.get('SIMULATOR_SETTINGS_MODULE'))
global_config = importlib.import_module(os.environ.get('GLOBAL_CONFIG_MODULE'))


log_file = Path(global_config.LOGGING_ROOT) / \
    global_config.LOGGING_FILES_PATHS['workers']['simulator']

if not Path(log_file).parent.is_dir():
    Path(log_file).parent.mkdir(parents=True)


# We open the stderr separately from sys.stderr so
# that when python writes to sys.stderr it won't
# fall into an infinite loop of writing over and over.
stderr_stream = os.fdopen(2, 'w')

# We only use and configure the root logger.
# We catch all levels of logging.
# We use WatchedFileHandler to support log rotation by external tools.
logging.basicConfig(
    level=logging.DEBUG,
    format=f'[%(asctime)s $ {WORKER_NAME}] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(stream=stderr_stream),
        logging.handlers.WatchedFileHandler(
            filename=log_file,
            mode='a', encoding='utf-8'
        )
    ])

logging.info('Simulation worker started.')
logging.info(f'> worker pid: {os.getpid()}')


# Note:
#   - The writes to stderr are partial and don't
#     always end in a newline, but the logging
#     methods do automatically append the newline.
#   - We discard more than one newline, if any exists.
last_line = ''
def write_error_with_log(s):
    global last_line
    
    if s.endswith('\n'):
        logging.critical(last_line + s.rstrip('\n'))
        last_line = ''
    else:
        last_line += s


# We want to write the errors to the log too. It will
# will show up in both log handlers: the stderr (fd 2)
# and the log file.
sys.stderr.write = write_error_with_log


# Import/load all the game classes, so they are
# all ready when needed to be accessed. We import
# the module separately so that we can use reload()
# on it.
games_index = importlib.import_module(settings.GAMES_INDEX_MODULE)
GAME_CLASSES = games_index.GAME_CLASSES

logging.info('Game classes have been loaded.')
logging.info(f'> games list: {list(GAME_CLASSES.keys())}')

# We use a signal handler to make the worker refresh
# the game classes if they have been changed. This
# way, we don't have to restart the worker.
def reload_game_classes(*args, **kwargs):
    global GAME_CLASSES
    
    importlib.reload(games_index)
    GAME_CLASSES = games_index.GAME_CLASSES
    
    logging.info('Game classes have been refreshed by a '
                 f'{settings.GAME_CLASSES_RELOAD_SIGNAL.name}.')
    logging.info(f'> games list: {list(GAME_CLASSES.keys())}')

signal.signal(settings.GAME_CLASSES_RELOAD_SIGNAL, reload_game_classes)


# ensure_ascii is True by default but we emphasize here. It's
# so that we can still use the streams in text mode rather than
# binary mode, which means that when we try to get the length
# of a message, each character is actually one byte, and thus
# using it with the read() syscall won't cause problems.
json.dumps = functools.partial(
    json.dumps, 
    separators=(',', ':'),
    ensure_ascii=True
)


# The pipe fd numbers used by forked children.
tracer.set_forked_pipe_fds(settings.FORKED_PIPES_FDS['r'],
                           settings.FORKED_PIPES_FDS['w'])

# The pipe fd numbers used by the forkserver.
tracer.set_forkserver_pipe_fds(settings.FORKSERVER_PIPES_FDS['r'],
                               settings.FORKSERVER_PIPES_FDS['w'])

# Also defined in coderunner/run.py. Note that the
# version here MUST NOT contain the read() or the
# write() syscalls, whereas the one in run.py must.
tracer.set_allowed_syscalls(settings.PTRACE_ALLOWED_SYSCALLS)

tracer.set_write_max_bytes(settings.CHILD_MAX_WRITE_SIZE)


# Communicate through I/O streams, with enforced newlines
# and flushes.
class StreamTalker:
    def __init__(self, read_stream, write_stream, exc):
        self.read_stream = read_stream
        self.write_stream = write_stream
        self.exc = exc
    
    @classmethod
    def from_fd(cls, read_fd, write_fd, exc):
        read_stream = os.fdopen(read_fd, 'r', newline='\n')
        write_stream = os.fdopen(write_fd, 'w', newline='\n')
                
        return cls(read_stream, write_stream, exc)
    
    def send(self, msg):
        try:
            # Whether which one of these lines might
            # cause a BrokenPipeError depends on the
            # buffering, which we have NOT explicitly
            # specified in fdopen.
            self.write_stream.write(msg + '\n')
            self.write_stream.flush()
        except BrokenPipeError:
            raise self.exc
    
    def recv(self):
        res = self.read_stream.readline()
        
        # EOF is only hit if no writer to the pipe is left
        # (which is only one, namely, the coderunner child).
        # Once EOF is hit, the read() syscall returns.
        if not res:
            raise self.exc
        
        # discard the trailing '\n'
        return res[:-1] 


# We'll want everything in text form, so enable auto-decoding.
redis_client = redis.from_url(global_config.REDIS_SERVER_URL,
                              decode_responses=True)

docker_client = docker.DockerClient(base_url=global_config.DOCKER_SERVER_URL)

# If anything fails for the forkserver in the beginning, we
# won't log it directly, and rather let it simply error and exit.
# It will actually be logged as part of the stderr.

# fs: forkserver
fs_container = docker_client.containers.run(
    global_config.SIMULATOR_CODERUNNER['DOCKER_IMAGE'],
    detach=True,
    user=pwd.getpwnam(global_config.SIMULATOR_CODERUNNER['USERNAME']).pw_uid,
    security_opt=[
        f"apparmor={global_config.SIMULATOR_CODERUNNER['DOCKER_APPARMOR_PROFILE']}"
    ],
    read_only=True,
)

logging.info('Forkserver container started.')
logging.info(f'> forkserver container id: {fs_container.attrs["Id"]}')

# The forkserver must be the one and only process of the
# container, namely, the PID 1 (the init process) in the
# PID namespace of the container.
_fs_top = fs_container.top()
fs_pid = int(_fs_top['Processes'][0][_fs_top['Titles'].index('PID')])

logging.info(f'> forkserver pid: {fs_pid}')


# Attach to the forkserver and wait for it to stop.
#
# By tracing the forkserver, we are achieving four goals:
#
#   1) We can trace the forked children right from the beginning
#      when they get forked, thanks to PTRACE_O_TRACEFORK.
#   2) We can get the PID of forked children in the host's
#      PID namespace without having to resort to "docker top"
#      or similar things.
#   3) By setting the ptrace option PTRACE_O_EXITKILL, if this
#      process (the tracer) dies, the forkserver will also die,
#      and since it's the init process of the container, this
#      will also cause the forked children to die (we set the
#      EXITKILL option on the forked children too, but that is
#      not enough since the tracer might die before we set this
#      option on the forked child).
#   4) We wait for the forkserver to set up its pipe before we
#      try and communicate with it. This is done by waiting for
#      the first read() call of the forkserver on its side of
#      the pipe that it created (which we use the fd 0 for that).
#      the forkserver does this read after creating its pipes.
#      Note that the forkserver most likely does not even has
#      the fd 0 open by default (because we have not set the
#      option stdin_open=True for the container); instead, it
#      uses dup2() to make the fd's 0 and 1 to the proper ends
#      of the pipes it created.
#
# This doesn't really affect the performace, because we don't
# trace the syscalls or CPU instructions of the forkserver after
# the pipe initialization phase (where we need to trace the
# forkserver to see when read() is called); we only trace the
# fork events, and the signals it gets.
tracer.forkserver_attach(fs_pid)

# After the first read, the forkserver should have set up its
# pipes, so that we can pidfd_getfd() them after this.
tracer.forkserver_wait_first_read(fs_pid)

fs_pidfd = os.pidfd_open(fs_pid)
fs_read_fd = tracer.pidfd_getfd(fs_pidfd, settings.FORKSERVER_PIPES_FDS['_r'])
fs_write_fd = tracer.pidfd_getfd(fs_pidfd, settings.FORKSERVER_PIPES_FDS['_w'])

fs_talker = StreamTalker.from_fd(fs_read_fd, fs_write_fd, 
                                 ForkServer_UnknownKill)

fs_talker.send(settings.CC_F_CONTINUE)

logging.info('Successfully connected to the forkserver pipes.')


# lookup once
fs_send = fs_talker.send
fs_recv = fs_talker.recv


# Coderunner Controller
class CRController:
    def __init__(self, code, game_settings, limits):
        is_setup = False
        
        # Conventions on these exceptions:
        #   1) We don't kill the process before raising
        #      the exception. It has to be done by this
        #      worker AFTER the error (except when it's
        #      an UnknownKill, meaning that it's already
        #      dead).
        #   2) If an UnknownKill error contains an arg
        #      for explanation, then the kill has happened
        #      while the process was being traced. If
        #      no arg is present, then the kill happened
        #      before attaching to the process.
        #   3) For exceptions other than UnknownKills,
        #      if there is an explanation arg supplied,
        #      we take it, but otherwise we don't try
        #      to get explanation through waitpid. All
        #      we do, is kill by SIGKILL and waitpid to
        #      get rid of the zombie.
        try:
            fs_send(settings.CC_F_FORK_CHILD)
            
            # Wait for stop due to fork().
            tracer.forkserver_wait_stop(fs_pid)
            
            child_pid = tracer.forkserver_get_forked_pid(fs_pid)
            self.pid = child_pid
            
            # After fork(), both the forkserver and the forked
            # child will be stopped by ptrace, which is the effect
            # caused by the PTRACE_O_TRACEFORK option.
            tracer.forkserver_resume(fs_pid)
            
            # icns: in-container namespace. This is the pid of
            # the forked child in the PID namespace of the container.
            self.icns_pid_str = fs_recv()
            
            # I used to think that since a forked child is stopped from
            # the very beginning, stop-requiring requests like PTRACE_SYSCALL
            # would immediately work on them. Turns out, I was wrong and
            # we should be waiting for the waitpid() stop status first.
            # I haven't seen anything about this in the ptrace manual and
            # I'm still unsure of what's going on. Below we consume the 
            # waitpid() stop status before moving on.
            tracer.forked_wait_initial_stop(child_pid)
            
            # After the first read is hit, we know that the pipes are set up,
            # so we can do pidfd_getfd().
            tracer.forked_resume_until_read(child_pid)
            
            child_pidfd = os.pidfd_open(child_pid)
            self.pidfd = child_pidfd
            
            child_r_fd = tracer.pidfd_getfd(child_pidfd, settings.FORKED_PIPES_FDS['_r'])
            child_w_fd = tracer.pidfd_getfd(child_pidfd, settings.FORKED_PIPES_FDS['_w'])
            
            if child_r_fd == -1 or child_w_fd == -1:
                # The only way we might fail to get the established fd's
                # from a coderunner child is for it to be killed by SIGKILL.
                # Any other signal will cause a ptrace-stop (or continuation).
                raise Forked_UnknownKill
            
            self.r_fd = child_r_fd
            self.w_fd = child_w_fd
            
            child_talker = StreamTalker.from_fd(child_r_fd, child_w_fd,
                                                Forked_UnknownKill)

            resource.prlimit(child_pid, resource.RLIMIT_AS, (limits['mem_bytes'],)*2)
            
            child_talker.send(json.dumps(
                {'cpu_sec': limits['cpu_sec'], 'cpu_nsec': limits['cpu_nsec'],
                'code': code, 'context': game_settings}
            ))
            
            # -1 means don't impose any limit on the read size.
            tracer.forked_resume_read_SE(child_pid, -1)
            
            # Resume until the final read() before starting the simulation.
            tracer.forked_resume_until_read(child_pid)
            
            child_talker.send(settings.CC_C_START_SIMULATION)
            
            # Stop at the syscall-exit-stop of the read(). Basically
            # getting ready to run forked_trace_until_rw().
            tracer.forked_resume_read_SE(child_pid, -1)
            
            
            # **************** The Zone of Distrust ****************
            # Anything after this point that comes from the forked
            # child should be treated as untrusted, and there is no
            # no guarantee as to what the coderunner process will do.
            #
            # In the codes below, we only care about the behavior of
            # the forked child; we don't care even if any of that is
            # from an attacker. If the behavior, at any point, proves
            # to be against what is expected, the child would be
            # terminated.
            # ******************************************************
            
            is_setup = True
            
            # The following comments on what the read() and write()
            # are for assume that the coderunner has not been sabotaged
            # by an attacker.
            
            # Next expected r/w: write() with syscall code 1.
            # This write should acknowledge a successful run of the
            # initial code, as well as the existence of the 'Main' class.
            tracer.forked_trace_until_rw(child_pid, 1)
            
            # Resume the aforementioned write() and stop the child before
            # returning from the syscall, i.e., on the syscall-exit-stop event.
            tracer.forked_resume_write_SE(child_pid)
            
            # Next expected r/w: read() with syscall code 0.
            # This read() is for getting the next command (function and
            # args) for the forked child.
            tracer.forked_trace_until_rw(child_pid, 0)
            
            # We can finally read what the "acknowledgement" write()
            # has written for us. If an attacker somehow manages to
            # change the value of this write, then just terminate the
            # child.
            if child_talker.recv() != settings.CC_C_CHILD_READY:
                raise Forked_CodeSabotage('no CC_C_CHILD_READY')
            
            # At this point, the child is ready to accept commands
            # and execute them.
            
            self.is_alive = True
            self._talker = child_talker
            
            return

        # The exceptions are ordered from the most likely to
        # the least likely.
        #
        # Note that a ProcessLookupError cannot happen, because
        # the forked children will stay around as zombies even
        # if they get killed until their status is read, and the
        # calls like pidfd_open() or setrlimit() will not raise
        # errors on zombie processes.
        #
        # In case a ForkServer_* error happens, we let it simply
        # error out (which also logs it) and exit this worker.
        except Forked_IllegalSyscall as e:
            termination_reason = TerminationReasons.ILLEGAL_SYSCALL
            exc_args = e.args
        except Forked_UnknownSignal as e:
            termination_reason = TerminationReasons.UNKNOWN_SIGNAL
            exc_args = e.args
        except Forked_ENOMEM as e:
            termination_reason = TerminationReasons.ENOMEM
            exc_args = e.args
        except Forked_UnknownKill as e:
            termination_reason = TerminationReasons.UNKNOWN_KILL
            exc_args = e.args
        except Forked_CodeSabotage as e:
            termination_reason = TerminationReasons.SABOTAGE
            exc_args = e.args
        except Forked_UnexpectedCont as e:
            termination_reason = TerminationReasons.UNEXP_CONT
            exc_args = e.args
        
        self.finish_after_error(termination_reason, exc_args, is_setup)

    def finish_after_error(self, termination_reason, exc_args, is_setup):
        if exc_args:
            explanation = exc_args[0]
        else:
            explanation = None
        
        # The only possibilities for an unknown kill are by a SIGKILL
        # or seccomp's SIGSYS, and we consume the waitpid() and include
        # it in the args of the exception. Therefore, doing a kill() or
        # waitpid() would fail in this case.
        #
        # Note that for a seccomp kill, os.WIFSIGNALED actually gives True.
        if termination_reason == TerminationReasons.UNKNOWN_KILL:
            # When we raise an UnknownKill error, if we don't include
            # the explanation arg for the exception, it means that the
            # kill happened before attaching to the process.
            
            # Note that seccomp shouldn't really ever be triggered
            # because the tracer takes care of the illegal syscalls,
            # unless the syscall was called before actually running
            # the player code (i.e., during the setup), which indicates
            # a bug that should be fixed. Also if someone improperly
            # changes the simulator/settings.py for allowed syscalls
            # (in such a way that the set of allowed syscalls for seccomp
            # differs from that of the ptrace) it can also cause seccomp
            # to trigger.
            #
            # Also note that even though it appears that the termination
            # signal was SIGSYS, it does not trigger a ptrace-stop and
            # causes a kill instead.
            if os.WTERMSIG(explanation) == signal.SIGSYS.value:  # seccomp
                termination_reason = TerminationReasons.SECCOMP
        else:
            os.kill(self.pid, signal.SIGKILL.value)
            os.waitpid(self.pid, settings.WAITPID_FLAGS)
        
        
        # Check if we know about the "unknown" signal.
        if termination_reason == TerminationReasons.UNKNOWN_SIGNAL and explanation is not None:
            sig = os.WSTOPSIG(explanation)
            
            if sig == settings.CPU_TIME_EXCEED_SIGNAL.value:
                termination_reason = TerminationReasons.XCPUTIME

        # Wait stop due to SIGCHLD. This also consumes
        # the status so that we don't confuse it later.
        os.waitpid(fs_pid, settings.WAITPID_FLAGS)  
        
        # Resume after signal-stop due to SIGCHLD.
        tracer.forkserver_resume(fs_pid)
        
        # Get rid of the zombie. We use the pid in the
        # namespace of the container. According to the
        # ptrace manual, after a death/exit waitpid status
        # is consumed by the tracer, the real parent will
        # be given the status/notification. Once the parent
        # consumes the status too, the zombie goes away.
        fs_send(self.icns_pid_str)

        # If a coderunner child gets killed before any code is
        # run, then it's a problem on our side. We report the
        # incident, but still let the simulation continue.
        if not is_setup:
            logging.error('A coderunner child has been killed '
                            'before its setup is over.')
            logging.error(f'> coderunner pid: {self.pid}')
            logging.error(f'> termination reason: {termination_reason}')
            logging.error(f'> explanation: {explanation}')
            logging.error(f'> forkserver container id: {fs_container.attrs["Id"]}')

        # Cleanup the file descriptors.
        for fdn in ['pidfd', 'r_fd', 'w_fd']:
            fd = getattr(self, fdn, None)
            if fd:
                os.close(fd)

        self.is_alive = False
        
        # The 'explanation' is the one and only arg of the
        # exception, and it can be empty.
        #
        # It can be either of the following:
        #   - A waitpid() status that caused the error.
        #   - a 3-tuple. The first number is the syscall
        #     number, and if the syscall was either of
        #     read() or write(), the rest of the items
        #     are the 1st and the 3rd args of the syscall.
        #     For other syscalls, the rest are both -1.
        #     This is used for Forked_IllegalSyscall exceptions.
        #     The reason for 1st and 3rd args is because
        #     read() and write() are allowed under special
        #     conditions, and these two args determine part
        #     of their condition. Other syscalls are either
        #     totally allowed or totally disallowed.
        #   - The Python None. In case of UnknownKill,
        #     this indicates that the kill happened before
        #     attaching to the process. In other cases,
        #     it means that the cause of the exception was
        #     not some unexpected waitpid status (e.g.,
        #     ENOMEM, ...) and thus a waitpid status is
        #     irrelevant. Also note that the worker will
        #     send a SIGKILL in the end anyways.
        self.error_report = (termination_reason, explanation)
    
    def run_command(self, f_name, f_args):
        # This function may return either of these:
        #   - a 1-tuple, containing a result of a successful
        #     execution of the command.
        #   - -1. This means that the player's function
        #     raised an exception.
        #   - The Python None. This means that the player has
        #     been eliminated. 
        
        message = json.dumps({'f': f_name, 'args': f_args})
        
        try:
            self._talker.send(message)
            
            # +1 for the newline character
            tracer.forked_resume_read_SE(self.pid, len(message)+1)
            
            # Next expected r/w: write() with syscall code 1.
            tracer.forked_trace_until_rw(self.pid, 1)
            
            tracer.forked_resume_write_SE(self.pid)
            
            # Next expected r/w: read() with syscall code 0.
            tracer.forked_trace_until_rw(self.pid, 0)
            
            output = json.loads(self._talker.recv())
            
            # We always return a dict JSON from the coderunner,
            # unless an attacker has changed it to something
            # else (e.g., int, float, NaN, ...).
            if not isinstance(output, dict):
                raise Forked_CodeSabotage('output not dict')
            
            if 'result' in output:
                # We return a tuple just to be sure that it's
                # distinguished from returning None and -1.
                return (output['result'],)
            else:
                # An exception happened in the player code. We
                # simply ignore it.
                return -1  # means exception
        except Forked_IllegalSyscall as e:
            termination_reason = TerminationReasons.ILLEGAL_SYSCALL
            exc_args = e.args
        except Forked_UnknownSignal as e:
            termination_reason = TerminationReasons.UNKNOWN_SIGNAL
            exc_args = e.args
        except Forked_ENOMEM as e:
            termination_reason = TerminationReasons.ENOMEM
            exc_args = e.args
        except Forked_UnknownKill as e:
            termination_reason = TerminationReasons.UNKNOWN_KILL
            exc_args = e.args
        except Forked_CodeSabotage as e:
            termination_reason = TerminationReasons.SABOTAGE
            exc_args = e.args
        except Forked_UnexpectedCont as e:
            termination_reason = TerminationReasons.UNEXP_CONT
            exc_args = e.args
        except JSONDecodeError:
            # If the untrusted code somehow manages to mess with
            # the code we've written for the forked child, then
            # it's a sabotage. In the coderunnre child we always
            # try to return a valid JSON, even on exceptions.
            termination_reason = TerminationReasons.SABOTAGE
            exc_args = ('JSONDecodeError',)
        
        self.finish_after_error(termination_reason, exc_args, True)
        return None  # means that the player coderunner has been terminated.
    
    def finish_after_simulation(self):
        # Will not fail, even if the forked child is killed
        # before this and after the simulation. This is because
        # it will remain as a zombie process for us to get its
        # wait status.
        os.kill(self.pid, signal.SIGKILL.value)
        os.waitpid(self.pid, settings.WAITPID_FLAGS)

        # See the comments in 'finish_after_error' for an
        # explanation of the following.
        os.waitpid(fs_pid, settings.WAITPID_FLAGS)
        tracer.forkserver_resume(fs_pid)
        
        fs_send(self.icns_pid_str)

        # Cleanup the file descriptors. Since this is a
        # successful finish, all these fd's must exist.
        os.close(self.pidfd)
        os.close(self.r_fd)
        os.close(self.w_fd)
        
        # We don't need this anymore, but still ... .
        self.is_alive = False


def get_code(filename):
    try:
        with open(settings.MEDIA_ROOT / filename) as f:
            return f.read()
    # If the player uploads a bytes-formatted file,
    # just return an empty string as the code.
    except UnicodeDecodeError:
        return ''


def process(message):
    message_id, serialized_data = message
    
    data = json.loads(serialized_data['data'])
    
    fight_id = data['fight_id']
    game_settings = data['game_settings']
    codes_filenames = data['codes_filenames']
    player_count = len(codes_filenames)

    game = GAME_CLASSES[data['game']](
        game_settings=game_settings,
        player_count=player_count
    )
    
    # Memory and CPU time limits
    limits = game.get_limits()
    
    cr_controllers = []
    initial_players = []
    
    for player_index in range(player_count):
        player_code = get_code(codes_filenames[player_index])
        
        # TODO: maybe also let the game give each player's Main instance
        # extra context (e.g., by appending it to "context", which is
        # currently only the game settings). Even though we can still
        # tell the player to define a certain function that can be called
        # by the game in the beginning and give the context to it so
        # that the player can save it, but that would mean that the player
        # has to write more code.
        crc = CRController(player_code, game_settings, limits)
        cr_controllers.append(crc)
        
        if crc.is_alive:
            initial_players.append(player_index)
    
    game.set_controllers(cr_controllers, initial_players)
    
    game.simulate()
    
    final_states = []
    for c in game.cr_controllers:
        if c.is_alive:
            c.finish_after_simulation()
            final_states.append(0)  # 0 means a successful finish
            continue
        
        final_states.append(c.error_report)
    
    output_data = {'fight_id': fight_id,
                   'report': game.get_report(),
                   'final_states': final_states}

    redis_client.xadd(global_config.REDIS_RESULT_PROCESSOR_STREAM,
        {'data': json.dumps(output_data)}
    )

    redis_client.xack(global_config.REDIS_SIMULATOR_STREAM,
                      global_config.REDIS_SIMULATOR_GROUP,
                      message_id)


# The worker might crash while some simulations have
# not been acknowledged yet (which shouldn't really
# be more than one per worker). We redo those simulations.
unacked = redis_client.xreadgroup(
        groupname=global_config.REDIS_SIMULATOR_GROUP,
        consumername=WORKER_NAME,
        streams={global_config.REDIS_SIMULATOR_STREAM: '0'},
)[0][1]  # get for the one and only relevant stream.

for msg in unacked:
    process(msg)


while True:
    query = redis_client.xreadgroup(
        groupname=global_config.REDIS_SIMULATOR_GROUP,
        consumername=WORKER_NAME,
        streams={global_config.REDIS_SIMULATOR_STREAM: '>'},  # only the new messages
        block=0,  # block until a new message arrives.
        count=1
    )[0]  # get for the one and only relevant stream.
    
    # Process the one and only message.
    process(query[1][0])
