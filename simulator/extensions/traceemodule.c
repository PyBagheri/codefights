#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <signal.h>
#include <unistd.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <seccomp.h>  // we need libseccomp
#include <err.h>


// For seccomp sandboxing (using libseccomp), see the following:
// 1. https://blog.cloudflare.com/sandboxing-in-linux-with-zero-lines-of-code/
// 2. https://github.com/seccomp/libseccomp/blob/main/src/python/seccomp.pyx
//    [the beginning docstrings on necessary python syscalls. Note that
//     we won't need all of the syscalls mentioned.]


static PyObject *
tracee_start_cputime_timer(PyObject *self, PyObject *args, PyObject *kwargs) {
    int signal;
    time_t interval_sec;
    time_t interval_nsec;
    time_t initial_sec;
    time_t initial_nsec;

    char *kwlist[] = {"signal", "interval_sec", "interval_nsec", "initial_sec", 
                      "initial_nsec", NULL};

    // 'time_t' is of type 'long int'. Parsing to int makes timer_settime()
    // raise EINVAL (invalid argument).
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "illll:start_cputime_timer", kwlist, 
            &signal, &interval_sec, &interval_nsec, &initial_sec, &initial_nsec)) {
        return NULL;
    }

    timer_t tid;
    struct sigevent sev = {{SIGEV_SIGNAL}, signal};

    struct timespec interval = {interval_sec, interval_nsec};
    struct timespec initial = {initial_sec, initial_nsec};

    const struct itimerspec ispec = { interval, initial };

    timer_create(CLOCK_PROCESS_CPUTIME_ID, &sev, &tid);

    if (timer_settime(tid, TIMER_ABSTIME, &ispec, NULL) == 0) {  // success
        return PyLong_FromLong(0);
    } else {
        exit(1);  // just don't bother staying around if timers don't work.
    }
}


static PyObject *
tracee_apply_seccomp(PyObject *self, PyObject *args) {
    PyObject *syscalls_tuple;

    if (PyArg_ParseTuple(args, "O:apply_seccomp", &syscalls_tuple)) {
        if (!PyTuple_CheckExact(syscalls_tuple)) {
            PyErr_SetString(PyExc_TypeError, "The argument must be a tuple.");
            return NULL;
        }
    } else {
        return NULL;
    }

    Py_ssize_t n = PyTuple_Size(syscalls_tuple);

    /* disallow all syscalls by default. */
    scmp_filter_ctx seccomp_ctx = seccomp_init(SCMP_ACT_KILL_PROCESS);
    if (!seccomp_ctx)
        err(1, "seccomp_init failed");

    for (int i = 0; i < n ; i++) {
        PyObject *next = PyTuple_GetItem(syscalls_tuple, i);

        PyObject *encoded = PyUnicode_AsEncodedString(next, "UTF-8", "strict");
        if (!encoded) {
            exit(1);
        }

        char *syscall = PyBytes_AsString(encoded);
        if (!syscall) {
            exit(1);
        }

        if (seccomp_rule_add_exact(seccomp_ctx, SCMP_ACT_ALLOW, 
            seccomp_syscall_resolve_name(syscall), 0)) {
            perror("seccomp_rule_add_exact failed");
            exit(1);
        }
    }

    /* apply the composed filter */
    if (seccomp_load(seccomp_ctx)) {
        perror("seccomp_load failed");
        exit(1);
    }

    /* release allocated context */
    seccomp_release(seccomp_ctx);

    /* count as success */
    return PyLong_FromLong(0);
}


static PyMethodDef TraceeMethods[] = {
    {"start_cputime_timer", (PyCFunction)(void(*)(void))tracee_start_cputime_timer,
    METH_VARARGS | METH_KEYWORDS,
     "Start a CPU-time timer for the current process, given the expiry signal and times."},
     
    {"apply_seccomp", tracee_apply_seccomp, METH_VARARGS,
     "Apply the seccomp rules such that only the specified syscalls are allowed."},

    {NULL, NULL, 0, NULL}        /* Sentinel */
};


static struct PyModuleDef traceemodule = {
    PyModuleDef_HEAD_INIT,
    "tracee",   /* name of module */
    NULL,       /* module documentation */
    -1,
    TraceeMethods
};


PyMODINIT_FUNC
PyInit_tracee(void)
{
    return PyModule_Create(&traceemodule);
}
