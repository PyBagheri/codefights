// For more information and the sources, see the following:
// [1] https://man7.org/linux/man-pages/man2/ptrace.2.html
// [2] https://nullprogram.com/blog/2018/06/23/
// [3] https://eli.thegreenplace.net/2011/01/23/how-debuggers-work-part-1/
// [4] https://eli.thegreenplace.net/2011/01/27/how-debuggers-work-part-2-breakpoints/
// [5] https://pubs.opengroup.org/onlinepubs/9699919799/functions/V2_chap02.html
// [6] https://stackoverflow.com/questions/6468896/why-is-orig-eax
//
// These links are referred to throughout the code by their index.


#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <signal.h>
#include <sys/ptrace.h>
#include <sys/user.h>
#include <sys/errno.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/syscall.h>      /* Definition of SYS_* constants */
#include <sys/utsname.h>


// Only for x86_64.
#define SYSCALL_NUMBER(x) x.orig_rax
#define SYSCALL_ARG_1(x) x.rdi
#define SYSCALL_ARG_2(x) x.rsi
#define SYSCALL_ARG_3(x) x.rdx
#define SYSCALL_ARG_4(x) x.r10
#define SYSCALL_ARG_5(x) x.r8
#define SYSCALL_ARG_6(x) x.r9


// The actual max is much less. This is just to
// be sure. Plus, this is not based on a doc or
// something; it's just that I've seen the last
// syscall numbers for x86_64 to be in the ballpark
// of 500's, so 1024 should be fine.
#define MAX_SYSCALL_NUMBER 1024

// An index map for fast check/access.
static char allowed_syscalls_index_map[MAX_SYSCALL_NUMBER+1] = {0};

// The max 'count' argument for the write() syscall. This
// should be considerably less than the pipe size to avoid
// the forked child from writing too much into the pipe,
// which would cause the kernel to put it into an indefinite
// hang until the other end of the pipe (the worker) reads
// from it, but the worker doesn't expect to.
static int write_max_bytes = 0;

static PyObject *Py_Zero;

// set to -1 by default to avoid accidental problems.
static int forked_read_fd = -1, forked_write_fd = -1;
static int forkserver_read_fd = -1, forkserver_write_fd = -1;

#define WAITPID_FLAGS (__WALL)

// When we set the PTRACE_O_TRACESYSGOOD option, the
// 7th bit is set to help distinguish syscall traps
// from other traps. We check against this value.
#define SYSCALL_SIGTRAP (SIGTRAP|0x80)

#define STOPPED_CHECK_WRONG_0 (WSTOPSIG(status) != SIGSTOP)
#define STOPPED_CHECK_WRONG_1 (WSTOPSIG(status) != SYSCALL_SIGTRAP)
#define STOPPED_CHECK_WRONG_2 (WSTOPSIG(status) != SIGTRAP)

#define STOPPED_CHECK_WRONG(stop_strap_trap) STOPPED_CHECK_WRONG_ ## stop_strap_trap


// - Unknown Kill: a SIGKILL by AppArmor, manual kill or OS; or a
// SIGSYS by seccomp (which does not cause ptrace-stops). Note that
// the forkserver might only be killed by the OS or manually, because
// we don't do anything illegal in the forkserver, so it cannot be
// killed by AppArmor (even though IT IS monitored by AppArmor).
//
// - Unknown Signal: any "unexpected" signal other than SIGKILL or 
// seccomp's SIGSYS that might be sent by either CPU Timer, manual 
// signalling or the OS. Note that when a forked child dies, the
// forkserver gets a SIGCHLD, but we should PTRACE_CONT the forkserver
// after this to avoid getting ForkServer_UnknownSignal. Note that,
// anything other than SIGKILL or seccomp's SIGSYS will be caught by
// ptrace, so even if a signal's action is to kill the process, we 
// still get to see it in ptrace (even if the signal is ignored).
//
// - Unexpected Continuation: a SIGCONT is sent to the process when
// we didn't expect it. In fact, in this tracer, we never use waitpid()
// for waiting on "continuation", but rather we only wait for stops.
// Therefore, an unexpected continuation means that, before we get to
// see the process's stop, it's was sent a SIGCONT (is there any other
// way to "continue" a process? I don't know).
//
// - Tracer-monitored errors (IllegalSyscall and ENOMEM): the errors that
// are directly observed by this tracer. Obviously this  is only for the
// forked children. IllegalSyscall errors are either due to a syscall that
// is not allowed at all, or a read/write in the wrong order or with bad
// arguments (fd and byte count).
static PyObject *ForkServer_UnknownKill;     // EXCEPTION_0_UK
static PyObject *ForkServer_UnknownSignal;   // EXCEPTION_0_US
static PyObject *ForkServer_UnexpectedCont;  // EXCEPTION_0_UC
static PyObject *Forked_IllegalSyscall;      // used directly instead of macros
static PyObject *Forked_ENOMEM;              // used directly instead of macros
static PyObject *Forked_UnknownKill;         // EXCEPTION_1_UK
static PyObject *Forked_UnknownSignal;       // EXCEPTION_1_US
static PyObject *Forked_UnexpectedCont;      // EXCEPTION_1_UC

#define EXCEPTION_0_UK ForkServer_UnknownKill
#define EXCEPTION_0_US ForkServer_UnknownSignal
#define EXCEPTION_0_UC ForkServer_UnexpectedCont
#define EXCEPTION_1_UK Forked_UnknownKill
#define EXCEPTION_1_US Forked_UnknownSignal
#define EXCEPTION_1_UC Forked_UnexpectedCont

#define EXC_UNKNOWN_KILL(fs_or_f) EXCEPTION_ ## fs_or_f ## _UK
#define EXC_UNKNOWN_SIGNAL(fs_or_f) EXCEPTION_ ## fs_or_f ## _US
#define EXC_UNEXPECTED_CONT(fs_or_f) EXCEPTION_ ## fs_or_f ## _UC


#define MODULE_ADD_EXCEPTION(module, name)                    \
    name = PyErr_NewException("tracer." #name, NULL, NULL);   \
    Py_XINCREF(name);                                         \
    if (PyModule_AddObject(module, #name, name) < 0) {        \
        Py_XDECREF(name);                                     \
        Py_CLEAR(name);                                       \
        Py_DECREF(module);                                    \
        return NULL;                                          \
    }


#define EXC_WITH_ARG(EXC_CLASS, ARG)    \
    PyObject *_args = PyTuple_New(1);   \
    PyTuple_SetItem(_args, 0, ARG);     \
    PyErr_SetObject(EXC_CLASS, _args);                


// Once waitpid() returns without WNOHANG:
//
// - The child might be killed by SIGKILL or seccomp's SIGSYS. Note that
// WIFSIGNALED() is only true when the process was actually killed (not
// stopped or whatever) due to a signal. Also note that only SIGKILL 
// or seccomp's SIGSYS will cause an immediate kill; the rest will cause 
// the process to stop because it's being traced, and thus before the
// signal handler (which might be the default one) is run, the tracer
// gets a chance of inspection. SIGKILL may be from AppArmor, the OS, 
// a user, etc.
//
// - The child might be stopped (by literally any signal other than
// SIGKILL or seccomp's SIGSYS). If the signals are as expected, then
// it's normal, otherwise the signal was not from this tracer. To see
// what signal has caused this, the worker should use waitpid(). The
// waitpid() status can also be acquired by the forkserver (the parent).
//
// - If the child is not stopped, then the only remaining possiblity
// is that it has been continued (the child cannot exit, see below.).
// This means that, after the child was stopped because of a syscall
// or signal, someone else sent it a SIGCONT. This is not expected at
// all, and we rather end the process (the worker should).
//
// Note that the coderunner child is not allowed to exit on its
// own as we have disallowed the family of syscalls for exiting.
// Also it has only a single thread, see the ptrace manual, section
// "Death under ptrace" to see what this has to do with threads.
// By the way, if there is a bug in the coderunner that causes
// an exit (due to error or whatever) BEFORE we start monitoring
// it by ptrace and/or applying the seccomp rules, then we would
// get a Forked_UnexpectedCont because that's the 'else' below.
// We might later add an exception like *_BugExit to be used for
// these situations instead.
//
// We have used the PTRACE_O_TRACESYSGOOD, so that if we expect a
// syscall stop event, then we check the stop signal against the
// modified sigtrap: (SIGTRAP|0x80). This way we can tell if the
// SIGTRAP was sent from this tracer or not, and also if the event
// was actually a syscall stop event. Note that this is not available
// for singlestepping, only for syscalls. Also, in case we expect
// a SIGSTOP or a normal SIGTRAP, we can't tell if the signal was
// sent from the tracer or not, and we don't really bother checking
// that: IF this causes a problem, later ptrace requests will raise
// errors, and the problem can be seen there.
//
// Also, we don't check for the return value of waitpid(),
// since waitpid() without WNOHANG will never return -1 unless
// this tracer itself is interrupted by a signal, which we
// don't expect.
//
// The use of 'fs_or_f' is to distinguish if the process that we do
// waitpid() on is the forkserver or a forked child. This is so that
// we can raise different exceptions, and thus let our Python code
// know which one has died, so that we can act accordingly. Using
// exceptions rather than return values makes our the Python coes
// simpler: rather than having to put everything in a Python function
// (so that we can break by returning) and check every single tracer 
// function's return value, we just put everything in a try-except.
//
// stop_strap_trap: 0 for sigstop, 1 for syscall sigtrap, 2 for normal sigtrap.
// fs_or_f: 0 for forkserver, 1 for forked.
#define CHECK_WAITPID_STATUS(status, stop_strap_trap, fs_or_f)               \
    if (WIFSIGNALED(status)) {                                               \
        EXC_WITH_ARG(EXC_UNKNOWN_KILL(fs_or_f), PyLong_FromLong(status));    \
        return NULL;                                                         \
    } else if (WIFSTOPPED(status)) {                                         \
        if (STOPPED_CHECK_WRONG(stop_strap_trap)) {                          \
            EXC_WITH_ARG(EXC_UNKNOWN_SIGNAL(fs_or_f),                        \
                PyLong_FromLong(status));                                    \
            return NULL;                                                     \
        }                                                                    \
    } else {                                                                 \
        EXC_WITH_ARG(EXC_UNEXPECTED_CONT(fs_or_f),                           \
            PyLong_FromLong(status));                                        \
        return NULL;                                                         \
    }


// The only error code that we expect is ESRCH. Anything else is
// a sign of a bug and will be reported by a SystemError.
//
// From ptrace manual:
//   ESRCH  The specified process does not exist, or is not currently
//          being traced by the caller, or is not stopped (for
//          requests that require a stopped tracee).
//
// So we have these possibilities when we get ESRCH:
//
//   - If the request was for attaching (PTRACE_ATTACH, etc.), then
//     then only possibility of ESRCH is for the process to be already
//     dead before attempting to attach. This can only happen for the
//     forkserver, because the forked children are automatically traced
//     from the very beginning, due to the option PTRACE_O_TRACEFORK.
//     If this happens for the forkserver, then the following waitpid()
//     will simply return -1; It won't block forever.
//
// If waitpid() does not return -1, then the process was actually
// being traced, and we have:
//
//   - One possibility is that the process died (by a SIGKILL or seccomp's
//     SIGSYS). We check this by WIFSIGNALED().
//
//   - Another possibility is that the process was unexpectedly continued.
//     This means that the continuation happened AFTER our last waitpid()
//     check for stop (which we do before attempting each stopped-requiring
//     ptrace request).
//
//   - Getting stopped should not cause ESRCH.
//
//   - Neither the forkserver nor the forked children are allowed to exit
//     on their own, UNLESS due to a bug; in which case we just kill the
//     process and report the status as an unknown kill. We might later
//     add an exception like *_BugExit for these situations.
//
// Note that the waitpid() below will never block. if any problem has happened,
// it has happened after the last CHECK_WAITPID_STATUS and thus waitpid().
// Therefore there is another waitpid() notification to be consumed, and thus
// the waitpid() below will not block forever.
//
// Note that we could not have used the WNOHANG option, since, as explained
// in the ptrace manual, it would not be reliable. See the manual.
//
// NOTE: When using this macro, you MUST have declared an int named
// 'status' in the function.
#define CHECK_PTRACE_ERROR(r, pid, error_message_format, fs_or_f)          \
    if (r == -1) {                                                         \
        if (errno == ESRCH) {                                              \
            if (waitpid(pid, &status, WAITPID_FLAGS) == -1) {              \
                PyErr_SetNone(EXC_UNKNOWN_KILL(fs_or_f));                  \
            } else {                                                       \
                if (WIFSIGNALED(status)) {                                 \
                    EXC_WITH_ARG(EXC_UNKNOWN_KILL(fs_or_f),                \
                        PyLong_FromLong(status));                          \
                } else if (WIFCONTINUED(status)) {                         \
                    EXC_WITH_ARG(EXC_UNEXPECTED_CONT(fs_or_f),             \
                        PyLong_FromLong(status));                          \
                } else {                                                   \
                    kill(pid, SIGKILL);                                    \
                    EXC_WITH_ARG(EXC_UNKNOWN_KILL(fs_or_f),                \
                        PyLong_FromLong(status));                          \
                }                                                          \
            }                                                              \
            return NULL;                                                   \
        } else {                                                           \
            kill(pid, SIGKILL);                                            \
            char error_message[100];                                       \
            snprintf(error_message, 100, error_message_format, errno);     \
            PyErr_SetString(PyExc_SystemError, error_message);             \
            return NULL;                                                   \
        }                                                                  \
    }


// Syscall numbers are fixed and don't change.
// The %rax register (for x86_64) will be set
// to the syscall number and we check against it.
//
// This MUST NOT check either of 'read' or 'write'
// syscalls; For player codes, they are considered
// illegal syscalls (even though they might get around
// it, but that doesn't matter) and are particularly
// controlled by the tracer to avoid indefinite hangs
// with no response.
#define IS_SYSCALL_ALLOWED(syscall_code)  \
    (allowed_syscalls_index_map[syscall_code] == 1)


// This macro checks if the given syscall
// generates an ENOMEM (Not enough memory) in
// case of memory shortage (we set the memory
// limit of the code runner using prlimit()).
//
// mmap:     9
// brk:     12
// mremap:  25
//
// **WARNING**: We MUST check if the syscall is
// allowed itself. Some of these syscalls may 
// not even be allowed, let alone checking if
// they have raised ENOMEM.
#define SYSCALL_RAISES_ENOMEM(syscall_code)  \
    (syscall_code == SYS_mmap    ||          \
     syscall_code == SYS_brk     ||          \
     syscall_code == SYS_mremap)


static PyObject *
tracer_set_write_max_bytes(PyObject *self, PyObject *args) {
    int wmb;

    if (!PyArg_ParseTuple(args, "i:set_write_max_bytes", &wmb)) {
        return NULL;
    }

    write_max_bytes = wmb;

    return Py_Zero;
}


static PyObject *
tracer_set_allowed_syscalls(PyObject *self, PyObject *args) {
    PyObject *syscalls_tuple;

    if (PyArg_ParseTuple(args, "O:set_allowed_syscalls", &syscalls_tuple)) {
        if (!PyTuple_CheckExact(syscalls_tuple)) {
            PyErr_SetString(PyExc_TypeError, "The argument must be a tuple.");
            return NULL;
        }
    } else {
        return NULL;
    }

    int n = PyTuple_Size(syscalls_tuple);

    for (int i = 0; i < n; i++) {
        long res = PyLong_AsLong(PyTuple_GetItem(syscalls_tuple, i));
        if (res == -1) {
            return NULL;
        }

        if (res == SYS_read || res == SYS_write) {
            PyErr_SetString(PyExc_ValueError, 
            "The 'read()' and 'write()' syscalls must not be included; they "
            "are particularly controlled by this tracer and are not allowed "
            "for player codes.");

            return NULL;
        }

        if (res < 0 || res > MAX_SYSCALL_NUMBER) {
            char error_message[100];
            snprintf(error_message, 100, "The syscall number must be in "
                "the range 0 to %i, inclusive.", MAX_SYSCALL_NUMBER);

            PyErr_SetString(PyExc_ValueError, error_message);

            memset(allowed_syscalls_index_map, 0, sizeof(allowed_syscalls_index_map));

            return NULL;
        }

        allowed_syscalls_index_map[res] = 1;  // 1 means allowed.
    }

    return Py_Zero;
}


static PyObject *
tracer_set_forked_pipe_fds(PyObject *self, PyObject *args) {
    int r, w;

    if (!PyArg_ParseTuple(args, "ii:set_forked_pipe_fds", &r, &w)) {
        return NULL;
    }

    if (r < 0 || w < 0) {
        PyErr_SetString(PyExc_ValueError, "fd numbers must be non-negative.");
        return NULL; 
    }

    forked_read_fd = r;
    forked_write_fd = w;

    return Py_Zero;
}


static PyObject *
tracer_set_forkserver_pipe_fds(PyObject *self, PyObject *args) {
    int r, w;

    if (!PyArg_ParseTuple(args, "ii:set_forkserver_pipe_fds", &r, &w)) {
        return NULL;
    }

    if (r < 0 || w < 0) {
        PyErr_SetString(PyExc_ValueError, "fd numbers must be non-negative.");
        return NULL; 
    }

    forkserver_read_fd = r;
    forkserver_write_fd = w;

    return Py_Zero;
}


static PyObject *
tracer_forkserver_attach(PyObject *self, PyObject *args) {
    int r, status;

    // Error message format for unexpected ptrace errors.
    static const char *ptrace_unex_emf = 
        "forkserver_attach: ptrace(PTRACE_ATTACH) on the forkserver raised error code %i.";

    pid_t forkserver_pid;

    if (!PyArg_ParseTuple(args, "i:forkserver_attach", &forkserver_pid)) {
        return NULL;
    }

    // We need to use PTRACE_ATTACH rather than PTRACE_SEIZE
    // because we want to stop it. This is because we need to
    // trace the forkserver until the first read() is hit, which
    // is used to indicate that the forkserver pipes have been
    // set up.
    r = ptrace(PTRACE_ATTACH, forkserver_pid, 0, 0);
    CHECK_PTRACE_ERROR(r, forkserver_pid, ptrace_unex_emf, 0);

    waitpid(forkserver_pid, &status, WAITPID_FLAGS);
    CHECK_WAITPID_STATUS(status, 0, 0);
    
    r = ptrace(PTRACE_SETOPTIONS, forkserver_pid, 0,
        PTRACE_O_TRACEFORK | PTRACE_O_EXITKILL | PTRACE_O_TRACESYSGOOD);
    CHECK_PTRACE_ERROR(r, forkserver_pid, ptrace_unex_emf, 0);

    return Py_Zero;
}


static PyObject *
tracer_forkserver_wait_first_read(PyObject *self, PyObject *args) {
    int r, status;

    static const char *ptrace_unex_emf = 
        "forkserver_wait_first_read: ptrace on the forkserver raised error code %i.";

    pid_t pid;

    if (!PyArg_ParseTuple(args, "i:forkserver_wait_first_read", &pid)) {
        return NULL;
    }


    struct user_regs_struct regs;
    while (1) {
        r = ptrace(PTRACE_SYSCALL, pid, 0, 0);
        CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 0);

        waitpid(pid, &status, WAITPID_FLAGS);
        CHECK_WAITPID_STATUS(status, 1, 0);

        r = ptrace(PTRACE_GETREGS, pid, 0, &regs);
        CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 0);

        // Upon returning from a syscall (before returning to the
        // userspace code), only registers rax, rcx and r11 will
        // be subject to changes, and the rest will be preserved.
        // For this reason, even if we hit the read() syscall on
        // a syscall-exit-stop event, we can still see its args.
        // See:
        //   https://stackoverflow.com/questions/2535989/
        //   https://stackoverflow.com/questions/47983371/
        if (SYSCALL_NUMBER(regs) == SYS_read &&
                SYSCALL_ARG_1(regs) == (long long unsigned)forkserver_read_fd) {
            r = ptrace(PTRACE_CONT, pid, 0, 0);
            CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 0);

            return Py_Zero;
        }
    }
}


static PyObject *
tracer_forkserver_wait_stop(PyObject *self, PyObject *args) {
    pid_t forkserver_pid;

    if (!PyArg_ParseTuple(args, "i:forkserver_wait_stop", &forkserver_pid)) {
        return NULL;
    }

    // Wait for the forkserver to stop.
    int status;
    waitpid(forkserver_pid, &status, WAITPID_FLAGS);

    // We only expect the forkserver to be in a stopped
    // condition. Also, the forkserver shall never exit
    // on its own. It also has only one thread (see the
    // ptrace manual, "Death under ptrace" for what this
    // has to do with threads). Therefore, the only other
    // status for the forkserver is for it to be unexpectedly
    // killed, either by AppArmor, or manually or by the OS.
    // The forkserver will receive a normal SIGTRAP upon fork.
    CHECK_WAITPID_STATUS(status, 2, 0);

    return Py_Zero;
}


static PyObject *
tracer_forkserver_get_forked_pid(PyObject *self, PyObject *args) {
    int status;

    static const char *ptrace_unex_emf = 
        "forkserver_get_forked_pid: ptrace on the forkserver raised error code %i.";

    pid_t forkserver_pid;

    if (!PyArg_ParseTuple(args, "i:forkserver_get_forked_pid", &forkserver_pid)) {
        return NULL;
    }

    unsigned long forked_pid;

    int r = ptrace(PTRACE_GETEVENTMSG, forkserver_pid, 0, &forked_pid);
    CHECK_PTRACE_ERROR(r, forkserver_pid, ptrace_unex_emf, 0);

    return PyLong_FromLong(forked_pid);
}


static PyObject *
tracer_forkserver_resume(PyObject *self, PyObject *args) {
    int status;

    static const char *ptrace_unex_emf = 
        "forkserver_resume: ptrace on the forkserver raised error code %i.";

    pid_t forkserver_pid;

    if (!PyArg_ParseTuple(args, "i:forkserver_resume", &forkserver_pid)) {
        return NULL;
    }

    // PTRACE_O_TRACEFORK will cause the tracee (the forkserver, in
    // this case) to be stopped, so we have to resume it after each
    // fork. This request should be sent from the worker.
    //
    // Also, when the forked children die, their parent (the
    // forkserver) will receive a SIGCHLD signal, which causes
    // a signal-stop for the forkserver. So, we'll have to resume
    // it again after a child dies.
    int r = ptrace(PTRACE_CONT, forkserver_pid, 0, 0);
    CHECK_PTRACE_ERROR(r, forkserver_pid, ptrace_unex_emf, 0);

    return Py_Zero;
}

static PyObject *
tracer_forked_wait_initial_stop(PyObject *self, PyObject *args) {
    int status;

    pid_t pid;

    if (!PyArg_ParseTuple(args, "i:forked_wait_initial_stop", &pid)) {
        return NULL;
    }

    waitpid(pid, &status, WAITPID_FLAGS);
    CHECK_WAITPID_STATUS(status, 0, 1);

    return Py_Zero;
}


static PyObject *
tracer_forked_resume_until_read(PyObject *self, PyObject *args) {
    int r, status;

    static const char *ptrace_unex_emf = 
        "forked_resume_until_read: ptrace on the forkserver raised error code %i.";

    pid_t pid;

    if (!PyArg_ParseTuple(args, "i:forked_resume_until_read", &pid)) {
        return NULL;
    }

    struct user_regs_struct regs;
    while (1) {
        r = ptrace(PTRACE_SYSCALL, pid, 0, 0);
        CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);

        waitpid(pid, &status, WAITPID_FLAGS);
        CHECK_WAITPID_STATUS(status, 1, 1);

        r = ptrace(PTRACE_GETREGS, pid, 0, &regs);
        CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);

        // Upon returning from a syscall (before returning to the
        // userspace code), only registers rax, rcx and r11 will
        // be subject to changes, and the rest will be preserved.
        // For this reason, even if we hit the read() syscall on
        // a syscall-exit-stop event, we can still see its args.
        // See:
        //   https://stackoverflow.com/questions/2535989/
        //   https://stackoverflow.com/questions/47983371/
        if (SYSCALL_NUMBER(regs) == SYS_read) {
            // Only allow read() from the specified fd.
            if (SYSCALL_ARG_1(regs) != (long long unsigned)forked_read_fd) {
                SYSCALL_NUMBER(regs) = -1;
                r = ptrace(PTRACE_SETREGS, pid, 0, &regs);
                CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);

                PyObject *status_tuple = PyTuple_New(3);
                PyTuple_SetItem(status_tuple, 0, PyLong_FromLong(SYS_read));
                PyTuple_SetItem(status_tuple, 1, PyLong_FromLong(SYSCALL_ARG_1(regs)));
                PyTuple_SetItem(status_tuple, 2, PyLong_FromLong(SYSCALL_ARG_3(regs)));

                EXC_WITH_ARG(Forked_IllegalSyscall, status_tuple);
                return NULL;
            }

            return Py_Zero;
        }
    }
}


static PyObject *
tracer_forked_trace_until_rw(PyObject *self, PyObject *args) { 
    // When we call this function, we should be stopped at a
    // syscall-exit-stop of a syscall, we this function lets
    // the process run until it hits the next read/write in 
    // the alternating sequence. That which one (read or write)
    // is the next, shall be given by the caller (the worker).

    // for storing ptrace() return value and waitpid() status.
    int r, status;

    static const char *ptrace_unex_emf = 
        "forked_trace_until_rw: ptrace on the forked child raised error code %i.";

    pid_t pid;
    int next_rw;

    if (PyArg_ParseTuple(args, "ii:forked_trace_until_rw", &pid, &next_rw)) {
        if (next_rw != 0 && next_rw != 1) {
            PyErr_SetString(PyExc_ValueError, 
            "The value of the second argument must be either 0 (for read) "
            "or 1 (for write).");

            return NULL;
        }
    } else {
        return NULL;
    }

    while (1) {
        // Resume from the syscall-exit-stop until the
        // next syscall (or signal).
        r = ptrace(PTRACE_SYSCALL, pid, 0, 0);
        CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);

        waitpid(pid, &status,  WAITPID_FLAGS);
        CHECK_WAITPID_STATUS(status, 1, 1);

        struct user_regs_struct regs;
        r = ptrace(PTRACE_GETREGS, pid, 0, &regs);
        CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);

        // This is only for the x86-64 architechture.
        // Since %rax is used both for storing the
        // syscall number and also the return value,
        // the original value is saved so that we,
        // as well as the kernel, have access to the
        // syscall number. See [2] and [6].
        int syscall_number = SYSCALL_NUMBER(regs);

        if (syscall_number == next_rw) {  // either read() or write()
            if (
                (syscall_number == SYS_read &&
                    SYSCALL_ARG_1(regs) != (unsigned long long)forked_read_fd
                ) ||
                (syscall_number == SYS_write &&
                   (SYSCALL_ARG_1(regs) != (unsigned long long)forked_write_fd ||
                    SYSCALL_ARG_3(regs) > (unsigned long long)write_max_bytes)
                )
            ) {
                // See the comments in the last 'else' block.
                SYSCALL_NUMBER(regs) = -1;
                r = ptrace(PTRACE_SETREGS, pid, 0, &regs);
                CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);

                PyObject *status_tuple = PyTuple_New(3);
                PyTuple_SetItem(status_tuple, 0, PyLong_FromLong(syscall_number));
                PyTuple_SetItem(status_tuple, 1, PyLong_FromLong(SYSCALL_ARG_1(regs)));
                PyTuple_SetItem(status_tuple, 2, PyLong_FromLong(SYSCALL_ARG_3(regs)));

                EXC_WITH_ARG(Forked_IllegalSyscall, status_tuple);
                return NULL;
            }

            return Py_Zero;
        } else if (IS_SYSCALL_ALLOWED(syscall_number)) {  // EXCLUDING read() and write()
            // We let the syscall run. Once the syscall exits and before 
            // it returns to the user-space code (the code runner child),
            // it will come here (tracer), and we can inspect the result
            // of the syscall. If the syscall is legal but not memory-related,
            // then this inspection is not necessary. For mem-related ones,
            // we'll check to see if ENOMEM has occured or not.
            r = ptrace(PTRACE_SYSCALL, pid, 0, 0);
            CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);
            waitpid(pid, &status,  WAITPID_FLAGS);
            CHECK_WAITPID_STATUS(status, 1, 1);

            if (SYSCALL_RAISES_ENOMEM(syscall_number)) {
                r = ptrace(PTRACE_GETREGS, pid, 0, &regs);
                CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);

                // the %rax register will refer to the return value
                // of the syscall. Again, this is another x86-64 thing.
                // Note that upon failure, a negative value is returned,
                // but since regs.rax is unsigned, the actual value 
                // starts from the end of its max. 
                if (regs.rax == -(unsigned long long)ENOMEM) {
                    // See the comments in the last 'else' block.
                    SYSCALL_NUMBER(regs) = -1;
                    r = ptrace(PTRACE_SETREGS, pid, 0, &regs);
                    CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);

                    PyErr_SetNone(Forked_ENOMEM);
                    return NULL;
                }
            }
        } else {  // illegal syscall.
            PyObject *status_tuple = PyTuple_New(3);
            PyTuple_SetItem(status_tuple, 0, PyLong_FromLong(syscall_number));
            PyTuple_SetItem(status_tuple, 1, PyLong_FromLong(-1));
            PyTuple_SetItem(status_tuple, 2, PyLong_FromLong(-1));

            // Change the syscall number to -1 (= invalid syscall) so
            // that the actual illegal syscall does not get executed.
            // I don't know if the syscall will get executed if we kill
            // the process with SIGKILL, so we keep this anyways to
            // prevent the syscall from actually being executed.
            SYSCALL_NUMBER(regs) = -1;
            r = ptrace(PTRACE_SETREGS, pid, 0, &regs);
            CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);

            EXC_WITH_ARG(Forked_IllegalSyscall, status_tuple);
            return NULL;
        }

        // Note that the child stops on a syscall-exit-stop
        // event so that we can manipulate the registers
        // before the syscall's result makes its way to the
        // user-space code (the code runner child). Once we're
        // done, in order to let the child run again and get
        // the syscall's results, we should run:
        //
        //     ptrace(PTRACE_SYSCALL, ...)
        //
        // which happens at the beginning of the next iteration
        // of the loop.
        //
        // ********* Sidetrack: Killing without SIGKILL *********
        // This is just an informative comment, and not really
        // used here. If a certain signal with the default action
        // of termination (other than SIGKILL or seccomp's SIGSYS) 
        // does not have a handler on the tracee, we could also send
        // that signal to the tracee and then PTRACE_DETACH from it
        // to let it continue to its death. This is possible because
        // PTRACE_DETACH sends a SIGCONT, which according to the POSIX
        // specs, first handles the queued, unblocked signals, and
        // then tries to run the actual process's code from where it
        // left off.
        //
        // I would like to explain another method to approach this
        // when we just want to let the signal be delivered to the
        // process and terminate it. Instead of:
        //
        //     ptrace(PTRACE_DETACH, pid, 0, 0);
        //
        // We could do this:
        //
        //    ptrace(PTRACE_SYSCALL, pid, 0, 0);
        //    waitpid(pid, 0, 0);
        //    ptrace(PTRACE_SYSCALL, pid, 0, THE_KILLER_SIGNAL_CODE);
        //
        // What is this and how does it work? We have:
        // 1) First of all, PTRACE_SYSCALL and PTRACE_SINGLESTEP,
        //    let the child continue but arrange for stopping at
        //    the next syscall or cpu instruction, repsecitvely.
        //    BUT, merely being traced is enough to arrange for stop
        //    at a signal delivery (even without any of those two
        //    requests). Thus, from the surface, you can't tell if
        //    the process was stopped because of a syscall or cpu
        //    instruction signal, or if it was because a signal was
        //    delivered.
        // 2) If we send the tracee a signal while it's stopped and
        //    before exiting the syscall-exit-stop, then, once we
        //    continue the process using PTRACE_SYSCALL, it's going
        //    to process the signal first before returning to the
        //    userspace code (the default behavior of SIGCONT; see [5]).
        //    This means that, we know for certain, that the next
        //    stop will be because of a signal.
        // 3) We do waitpid(pid, 0, 0) to wait for the signal-delivery
        //    -stop, which causes the tracee to be stop, so we can
        //    change/prevent the signal.
        // 4) On the next PTRACE_SYSCALL, we can use the 'data' arg
        //    to change the signal to be delivered, and then let the
        //    program continue. Rather than using a different signal,
        //    we just use the same signal that we initialy sent (not
        //    sure if we could use 0 for no change?!).
        // 5) The program receives SIGCONT, which, according to [5],
        //    will handle the signal first. Since we left the signal
        //    handler to be the system default (so that it terminates),
        //    the process gets terminated (in fact, it will become
        //    a zombie process until its exit code is read by the
        //    tracer as well as its parent, which is the forkserver.
        //    For this, the worker should also make a child status
        //    request to end the zombie process).
        //
        // As you can see, this just makes for redundant and longer
        // code. But it gives a good insight on how ptrace works.
        //
        // Another thing to mention is this quote from the ptrace man:
        //
        //     "exit/death by signal is reported first to the tracer,
        //     then, when the tracer consumes the waitpid(2) result, to
        //     the real parent"
        //
        // What we have to note about this is that if we detach from
        // the tracee (which lets it continue), then any signals that
        // the tracee will receive won't be seen by this tracer. Note
        // that those signals might also have been sent before detaching
        // and while the process was in stop (e.g., after a syscall-enter
        // -stop). In this case, we should ask the real parent to
        // provide us with the exit code and get rid of the zombie
        // process.
    }
}


// SE: stop on syscall exit (syscall-exit-stop).
static PyObject *
tracer_forked_resume_read_SE(PyObject *self, PyObject *args) {
    int r, status;

    static const char *ptrace_unex_emf = 
        "forked_resume_read_SE: ptrace on the forked child raised error code %i.";

    pid_t pid;
    int read_byte_count;

    if (!PyArg_ParseTuple(args, "ii:forked_resume_read_SE", &pid, &read_byte_count)) {
        return NULL;
    }

    // When 'read_byte_count' is -1, don't impose any limit
    // on the read size.
    if (read_byte_count != -1) {
        struct user_regs_struct regs;
        r = ptrace(PTRACE_GETREGS, pid, 0, &regs);
        CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);

        SYSCALL_ARG_3(regs) = read_byte_count;
        r = ptrace(PTRACE_SETREGS, pid, 0, &regs);
        CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);
    }

    r = ptrace(PTRACE_SYSCALL, pid, 0, 0);
    CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);

    waitpid(pid, &status, WAITPID_FLAGS);
    CHECK_WAITPID_STATUS(status, 1, 1);

    return Py_Zero;
}


// SE: stop on syscall exit (syscall-exit-stop).
static PyObject *
tracer_forked_resume_write_SE(PyObject *self, PyObject *args) {
    int r, status;

    static const char *ptrace_unex_emf = 
        "forked_resume_write_SE: ptrace on the forked child raised error code %i.";

    pid_t pid;

    if (!PyArg_ParseTuple(args, "i:forked_resume_write_SE", &pid)) {
        return NULL;
    }

    r = ptrace(PTRACE_SYSCALL, pid, 0, 0);
    CHECK_PTRACE_ERROR(r, pid, ptrace_unex_emf, 1);

    waitpid(pid, &status, WAITPID_FLAGS);
    CHECK_WAITPID_STATUS(status, 1, 1);

    return Py_Zero;
}


static PyObject *
tracer_pidfd_getfd(PyObject *self, PyObject *args) {
    int pidfd, fd;

    if (!PyArg_ParseTuple(args, "ii:pidfd_getfd", &pidfd, &fd)) {
        return NULL;
    }

    return PyLong_FromLong(syscall(SYS_pidfd_getfd, pidfd, fd, 0));
}


static PyMethodDef TracerMethods[] = {
    {"set_allowed_syscalls", tracer_set_allowed_syscalls, METH_VARARGS,
     "Set the allowed syscalls from a tuple of allowed syscall numbers. The "
     "argument must not contain the read() or the write() syscalls, as they "
     "are handled specifically and only allowed under certain conditions."},
     
    {"set_forked_pipe_fds", tracer_set_forked_pipe_fds, METH_VARARGS,
     "Set the pipe numbers that will be used by the forked coderunner."},

    {"set_forkserver_pipe_fds", tracer_set_forkserver_pipe_fds, METH_VARARGS,
     "Set the pipe numbers that will be used by the forkserver."},
    
    {"set_write_max_bytes", tracer_set_write_max_bytes, METH_VARARGS,
     "Set the max bytes that a write() by a forked child can write. This "
     "should be considerably smaller than the communication pipe size, "
     "so that the kernel doesn't put the forked child in a hang without "
     "the worker expecting so."},

    {"forkserver_attach", tracer_forkserver_attach, METH_VARARGS,
     "Attach to the forkserver and wait for it to stop, and thus start tracing "
     "it. To see what purposes this serves, see the comments in simulator/entry.py. "
     "This also has some side effects, including that the forkserver would be stopped "
     "when its children die, as it will get a SIGCHLD. See the comments for more "
     "information."},

    {"forkserver_wait_first_read", tracer_forkserver_wait_first_read, METH_VARARGS,
     "Wait until the forkserver tries to read from the given fd. This is used "
     "to detect when the forkserver is done setting up its pipes."},

    {"forkserver_resume", tracer_forkserver_resume, METH_VARARGS,
     "Let the stopped forkserver continue by sending it a SIGCONT. See the comments "
     "on when and how this should be used."},
     
    {"forkserver_wait_stop", tracer_forkserver_wait_stop, METH_VARARGS,
     "Wait until the forkserver is stopped, as being expected after a ptrace "
     "requets."},
     
    {"forkserver_get_forked_pid", tracer_forkserver_get_forked_pid, METH_VARARGS,
     "Get the pid of the child that just got forked off the forkserver. We use "
     "ptrace's features to get the pid rather than going for harder ways. Note "
     "that the PID that the forkserver would provide is on a different PID namespace "
     "than the host's PID namespace, so we cannot use that for tracing (but we "
     "need it for cleanups)"},
    
    {"forked_wait_initial_stop", tracer_forked_wait_initial_stop, METH_VARARGS,
     "Wait for the initial stop of the forked child. This is apparently necessary "
     "before making stop-requiring requests like PTRACE_SYSCALL."},
     
    {"forked_resume_until_read", tracer_forked_resume_until_read, METH_VARARGS,
     "Resume the forked child until a read() syscall with the set pipe fd "
     "is encountered. If used properly, this should stop on syscall-enter-stop."},

    {"forked_trace_until_rw", tracer_forked_trace_until_rw, METH_VARARGS,
     "Pass over the current syscall-exit-stop event (which is initially for the first "
     "read() syscall) and then actually start tracing syscalls on the child. Once "
     "we hit the expected one of read() or write(), stop the child and let the worker "
     "control how the read() or the write() should be handled. If a problem happens "
     "midway through, report it by an exception."},
     
    {"forked_resume_read_SE", tracer_forked_resume_read_SE, METH_VARARGS,
     "Pass over the syscall-entry-stop event of the current read() syscall "
     "and stop at the syscall-exit-stop of it."},
     
    {"forked_resume_write_SE", tracer_forked_resume_write_SE, METH_VARARGS,
     "Pass over the syscall-entry-stop event of the current write() syscall "
     "and stop at the syscall-exit-stop of it."},

    {"pidfd_getfd", tracer_pidfd_getfd, METH_VARARGS,
     "Basically a Python port for the syscall pidfd_getfd()."},

    {NULL, NULL, 0, NULL}        /* Sentinel */
};


static struct PyModuleDef tracermodule = {
    PyModuleDef_HEAD_INIT,
    "tracer",   /* name of module */
    NULL,       /* module documentation */
    -1,
    TracerMethods
};


PyMODINIT_FUNC
PyInit_tracer(void)
{
    struct utsname info;
    uname(&info);

    if (strcmp(info.machine, "x86_64") != 0) {
        PyErr_SetString(PyExc_SystemError, "The machine architechture must be x86_64. "
            "If you wish to change this, you must change the CPU register names "
            "for syscalls, etc. in the extension code accordingly.");
        return NULL;
    }

    int major, minor;
    if (sscanf(info.release, "%i.%i", &major, &minor) != 2) {
        PyErr_SetString(PyExc_SystemError, "Cannot read kernel version from uname.");
        return NULL;
    }

    // 5.6+: the syscall pidfd_getfd() is introduced. For older kernels, we'd
    //       need the older, longer logic for accessing file descriptors.
    // 4.8+: In versions 4.8+, seccomp is run after ptrace. It used to be the
    //       other way around, which is a serious bug. See:
    //       https://news.ycombinator.com/item?id=23067251
    if (major < 5 || (major == 5 && minor < 6)) {
        PyErr_SetString(PyExc_SystemError, "The kernel version must be 5.6 or higher.");
        return NULL;
    }

    PyObject *module = PyModule_Create(&tracermodule);

    MODULE_ADD_EXCEPTION(module, ForkServer_UnknownKill);
    MODULE_ADD_EXCEPTION(module, ForkServer_UnknownSignal);
    MODULE_ADD_EXCEPTION(module, ForkServer_UnexpectedCont);
    MODULE_ADD_EXCEPTION(module, Forked_IllegalSyscall);
    MODULE_ADD_EXCEPTION(module, Forked_ENOMEM);
    MODULE_ADD_EXCEPTION(module, Forked_UnknownKill);
    MODULE_ADD_EXCEPTION(module, Forked_UnknownSignal);
    MODULE_ADD_EXCEPTION(module, Forked_UnexpectedCont);

    Py_Zero = PyLong_FromLong(0);
    Py_INCREF(Py_Zero);  // we want it forever

    // might be NULL.
    return module;
}
