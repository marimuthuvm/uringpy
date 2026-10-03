"""Standalone build for the GIL probe (no liburing dependency).

    python3 benchmarks/setup_gilprobe.py build_ext --inplace

Builds only benchmarks/gilprobe so the experiment runs on any platform,
independent of the io_uring engine (which requires Linux + liburing).
"""

from setuptools import setup, Extension
from Cython.Build import cythonize

setup(
    name="gilprobe",
    ext_modules=cythonize(
        [Extension("gilprobe", sources=["benchmarks/gilprobe.pyx"],
                   extra_compile_args=["-O3"])],
        compiler_directives={"language_level": "3"},
    ),
)
