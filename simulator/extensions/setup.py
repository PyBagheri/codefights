from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            name="tracer",
            sources=["tracermodule.c"],
        ),
    ]
)
