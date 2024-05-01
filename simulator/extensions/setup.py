from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            name="tracee",
            sources=["traceemodule.c"],
            
            # The tracee module should have its dependencies (except
            # libc or similar system stuff) linked to it statically.
            # The last option is to disable static linking after that
            # (basically resetting the setting).
            extra_link_args=['-Wl,-Bstatic', '-lseccomp', '-Wl,-Bdynamic']
        ),
        
        Extension(
            name="tracer",
            sources=["tracermodule.c"],
        ),
    ]
)
