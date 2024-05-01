import os
_exit = os._exit   # ensure no cleanup.

# This script MUST not be run as root, as it will be running
# untrusted code. This script MUST be run as a user with very
# limited permissions. Besides anything that can go wrong with
# running this script as root, the process can change its
# seccomp rules after setting them if the running user is root.
if os.getuid() == 0:
    _exit(1)


import sys
import gc
import json
import functools
import fcntl

# The C extension for managing the tracee.
import tracee


from settings import (
    CHILD_PIPE_SIZE,
    
    FORKSERVER_PIPES_FDS,
    FORKED_PIPES_FDS,
    
    SECCOMP_ALLOWED_SYSCALLS,
    
    CPU_TIME_EXCEED_SIGNAL,
    
    # -------- Control codes --------
    
    # Used in the fork server.
    CC_F_FORK_CHILD,
    CC_F_CONTINUE,

    # Used in the children.
    CC_C_CHILD_READY,
    CC_C_START_SIMULATION,
    
    # -------------------------------
)


# These modules must be imported before applying seccomp rules,
# since there is a good change they won't be imported after, since
# we can no more access their source file. Note that AppArmor
# makes no problem here, since, in the profile, we allow access
# to all the builtin python library source files.
PRELOADED_MODULES = [
    'math',
    'cmath',
    'decimal',
    'random',
    'statistics',
    
    'collections',
    'heapq',
    'queue',
    'bisect',
    'graphlib',
    
    'enum',
    'functools',
    'itertools',
    'dataclasses',
    
    'uuid',
    'copy',
    'difflib',
]

for pm in PRELOADED_MODULES:
    sys.modules[pm] = __import__(pm)

# Should be kept while removing the unnecessary modules.
REQUIRED_MODULES = PRELOADED_MODULES + ['builtins', '__main__']


def build_talker(read_fd, write_fd): 
    # The reason we use closefd=False here is to prevent the forked children
    # from attempting to close the fd's of the forkserver's streams upon
    # garbage collection. For some reason (search later), when we delete
    # the 'os' module, the forkserver's stream objects get garbage collected
    # which triggers their __del__, which would turn attempts to close the
    # fd's if we had closefd=True (the default). The reason this would cause
    # problems is that we do the deletions after setting up seccomp (and
    # thus the garbage collection also happens after that), and seccomp
    # does not let us use the close() syscall.
    read_stream = os.fdopen(read_fd, 'r', newline='\n', closefd=False)
    write_stream = os.fdopen(write_fd, 'w', newline='\n', closefd=False)
    
    def send(msg):
        try:
            write_stream.write(msg + '\n')
            write_stream.flush()
        except BrokenPipeError:
            _exit(1)
    
    def recv():
        res = read_stream.readline()
        
        if not res:
            _exit(1)
            
        # discard the trailing '\n'
        return res[:-1]
    
    return recv, send


def child():
    # We'll delete these, so we need to 'global' them.
    global print, input, open, exit, quit, sys, PRELOADED_MODULES
    
    # Keep these before deleting the globals.
    jloads = json.loads
    jdumps = functools.partial(json.dumps, separators=(',', ':'), ensure_ascii=True)
    gcollect = gc.collect
    
    # Close all the fds that were inherited from the parent.
    # This should be done before dup2()ing the child fd's,
    # as they might use the same fd numbers.
    os.close(FORKSERVER_PIPES_FDS['r'])
    os.close(FORKSERVER_PIPES_FDS['w']) 
    
    # _r and _w will be the read and write fd's for the
    # worker process.
    r, _w = os.pipe()
    _r, w = os.pipe()
    
    # Remap the pipe fd's to fixed numbers for convenience.
    # The reason we also map the child (=this) side of the
    # pipe (i.e., r & w) is so that they can be used in the
    # tracer to restrict the read() and the write() syscalls
    # to only those file descriptors.
    os.dup2(r,  FORKED_PIPES_FDS['r'])
    os.dup2(_w, FORKED_PIPES_FDS['_w'])
    os.dup2(_r, FORKED_PIPES_FDS['_r'])
    os.dup2(w,  FORKED_PIPES_FDS['w'])
    
    # Don't keep the old fd's open.
    for _fd in (r, _w, _r, w):
        os.close(_fd)

    recv, send = build_talker(FORKED_PIPES_FDS['r'], FORKED_PIPES_FDS['w'])

    data = jloads(recv())
    
    fcntl.fcntl(FORKED_PIPES_FDS['w'], fcntl.F_SETPIPE_SZ, CHILD_PIPE_SIZE)
    
    player_code = data['code']
    context = data['context']  # currently only the game settings
    
    # Now that the required file descriptors are duplicated at the
    # worker (since we just used recv(), meaning that the parent
    # has got the fd's), we can close them here.
    os.close(FORKED_PIPES_FDS['_r'])
    os.close(FORKED_PIPES_FDS['_w'])
    
    # From this point on, only fd's FORKED_PIPES_FDS['r'] and FORKED_PIPES_FDS['w']
    # should be open, which are for the read and write of this tracee, respectively.
        
    if tracee.start_cputime_timer(CPU_TIME_EXCEED_SIGNAL.value,
                                  0, 0, data['cpu_sec'], data['cpu_nsec']) != 0:
        _exit(1)
    
    if tracee.apply_seccomp(SECCOMP_ALLOWED_SYSCALLS) != 0:
        _exit(1)
    

    # This prevents unallowed modules from being 'import'ed later.
    # Still, there are ways around this. For example, see:
    #  * https://stackoverflow.com/questions/33880646/access-module-sys-without
    # Again, this is just an added security, and NOT reliable on its own.
    # TODO: Maybe this really gives us no advantage at all. Check
    # and research later as to whether I should keep this. By the way,
    # note that seccomp will also disallows importing from source files.
    # Also I'm assuming that the preloaded modules either don't import
    # any other modules, or if they do, they can work without them.
    # I feel like just by accessing the module 'sys' one can somehow
    # refersh/load modules. I'm still unsure. Check later.
    module_names = list(sys.modules.keys())
    module_names.remove('sys')  # need it yet; will del later.
    for k in module_names:
        if k not in REQUIRED_MODULES:
            sys.modules[k] = None
    
    
    # We just get rid of the names, and remove their objects through
    # gc. This is just to make it more secure, but we CANNOT solely
    # rely on it to for security.
    for g in list(globals().keys()):
        if g not in ('__builtins__', '_exit', 'PRELOADED_MODULES', 'sys') and  \
            g not in PRELOADED_MODULES and  \
            not g.startswith('CC_C_'):  # Keep the control codes
                del globals()[g]
    
    del PRELOADED_MODULES
    
    
    # Local variables in Python are stored in arrays
    # rather than a dictionary, as an optimization; so
    # we have to take care of the local variables the
    # manual way.
    del module_names
    del g, k, _fd  # loop objects
    del r, _w, _r, w
    del data
    
    gcollect()
    del gcollect
    
    sys.modules['gc'] = None
    sys.modules['sys'] = None
    del sys
    
    assert not set(locals().keys()).difference(
        set(('jloads', 'jdumps', 'send', 'recv', 'player_code', 'context'))
    )
    
    # The reason we use CC_C_SIMULATION_START rather than
    # taking an empty line is to make sure that recv()
    # doesn't return because of a broken pipe. We could
    # also just take a single '\n' character for that,
    # but still a distinct code is better.
    if recv() != CC_C_START_SIMULATION:
        _exit(1)
    
    
    # *********************** The Zone of Distrust ***********************
    # After this point, we should basically imagine that the player's code
    # has complete control of the process, and any code other than the
    # player's code that comes below should just be considered an addition
    # or helper to the player's code. We MUST NOT rely on any of the 
    # following code to act in any expected way, at all. Anything that needs
    # to be imposed must be done through the tracer (aside from the seccomp
    # and cpu timer that we set above, which are OK, since they cannot be
    # changed after the seccomp rules are applied).
    #
    # One thing to note is that in the following code we use _exit to end
    # the process. The process doesn't end because _exit is meant to exit,
    # but because exit() and similar syscalls are illegal syscalls and the
    # seccomp or the tracer will catch this and kill the process.
    # ********************************************************************
    
    # Override some common builtins that the player might have accidentaly
    # used (e.g., for debugging), so that their process doesn't get killed
    # because of illegal syscalls.
    #
    # Note that if we don't specify the __builtins__ in the globals of the
    # exec, it will take the __builtins__ from its caller's globals.
    print = input = open = exit = quit = lambda *_args, **_kwargs: None
    
    # Run the player code.
    #
    # When we assign a name anywhere in Python, it gets assigned to the
    # locals(). The way we get module level assignments make their way
    # into the globals() is by having globals() and locals() be the same
    # object. Now, when it comes to exec(), since we specify the globals
    # and locals dicts, when a module-level assignment happens, it will
    # only be available in the locals() unless we pass the same dict
    # for both the globals() and the locals(). This also makes sense as
    # we're literally running a "module" that was uploaded by the player.
    # See https://stackoverflow.com/questions/2904274/
    ls = {}
    exec(player_code, ls, ls)
    
    # If the child exits (by error) *after* executing the code and
    # before running any functions, it means that the 'Main' class
    # does not exist. Note that the child doesn't exit on its own,
    # but by attempting an exit, it just triggers an illegal syscall,
    # which leads to the process being killed.
    main_class = ls.get('Main', None)
    if main_class is None:
        _exit(1)
    
    main_instance = main_class()
    
    # Set the context, so the player can access them through "self.context".
    # TODO: currently context contains only the game settings. Maybe later 
    # let game classes add their own extra context to be included.
    setattr(main_instance, "context", context)
    
    # Signaling the successful initial execution of the code and
    # initialization of the 'Main' object (which should be a class).
    #
    # This is useful when we use 'forked_trace_until_rw' as the
    # next write() in the alternating sequence of reads and writes.
    send(CC_C_CHILD_READY)
        
    # Some functions might be run many times. We store them
    # here to avoid looking them up again.
    resolved_names = {}
    
    while True:
        cmd = jloads(recv())
        
        func_name, args = cmd['f'], cmd['args']
        
        f = resolved_names.get(func_name, None)
        
        if f is None:    
            f = getattr(main_instance, func_name, None)
            if f is None: 
                _exit(1)  # Will be killed by seccomp or tracer.
        
            resolved_names[func_name] = f
        
        # We don't terminate the program in case of errors in
        # functions; instead, we give functions a chance to run
        # again; just for the fun of it ... . Isn't that how 
        # games and wars work? You might make a mistake, but
        # you still have a chance to pull a comeback.
        try:
            # We may note that the class body has been executed
            # in the context of the exec() above. This determines
            # the __globals__ attribute of the functions, which
            # are used to construct their frames before they are
            # run. Thus, their globals are those of the time they
            # were defined, not of the current line.
            send(jdumps({'result': f(*args)}))
        except BaseException:  # *might* be a JSON error from json.dumps().
            send("{}")  # an empty JSON, as a sign of exception.



# This module is not meant to be imported.
if __name__ == '__main__':
    # Just in case. Do before everything to
    # avoid fd number clashes.
    for _fd in (0, 1, 2):
        try:
            os.close(_fd)
        except OSError:
            pass
        
    
    r, _w = os.pipe()
    _r, w = os.pipe()


    # Remap these fd's so that we use the specified fixed numbers
    # in the worker. This is because the forkserver will not be
    # a child of the worker, so we could not connected to the
    # other end of the stdin or the stdout, therefore we created
    # the pipes instead and mapped them to fixed numbers, so that
    # the worker can pidfd_getfd() them.
    os.dup2(r,  FORKSERVER_PIPES_FDS['r'])
    os.dup2(_w, FORKSERVER_PIPES_FDS['_w'])
    os.dup2(_r, FORKSERVER_PIPES_FDS['_r'])
    os.dup2(w,  FORKSERVER_PIPES_FDS['w'])
    
    for _fd in (r, _w, _r, w):
        os.close(_fd)
    
    
    recv, send = build_talker(FORKSERVER_PIPES_FDS['r'], FORKSERVER_PIPES_FDS['w'])


    # Wait here and let the tracer see that we've hit a read().
    # This is to let the tracer/worker know that the forkserver
    # is done setting up its pipes, and that we can now start
    # the communication.
    if recv() != CC_F_CONTINUE:
        _exit(1)


    # Now that the required file descriptors are duplicated at the
    # worker (since we just used recv(), meaning that the parent
    # has got the fd's), we can close them here.
    os.close(FORKSERVER_PIPES_FDS['_r'])
    os.close(FORKSERVER_PIPES_FDS['_w'])
    
    # The only fd's that are inherited by children are
    # FORKSERVER_PIPES_FDS['r'] and FORKSERVER_PIPES_FDS['w'],
    # which MUST be closed by the children in the beginning.
    
    while True:
        cmd = recv()
        
        if cmd == CC_F_FORK_CHILD:
            res = os.fork()
            if res == 0:
                child()
                
                # if the child function returns (which shouldn't), exit.
                _exit(1)
            else:
                send(str(res))
        else:
            os.waitpid(int(cmd), 0)
