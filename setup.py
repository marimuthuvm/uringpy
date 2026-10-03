from setuptools import setup, Extension, find_packages
from Cython.Build import cythonize

extensions = [
    Extension(
        "uringpy.engine",
        sources=["uringpy/engine.pyx", "uringpy/slab.c"],
        libraries=["uring"],
        extra_compile_args=["-O3", "-march=native"],
        include_dirs=["uringpy"]
    )
]

setup(
    name="uringpy",
    version="0.1.0",
    author="Marimuthu Velayutham",
    description="High-Performance Asynchronous Zero-Copy Runtime for Python using Linux io_uring",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    ext_modules=cythonize(extensions, compiler_directives={'language_level': "3"}),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Topic :: System :: Networking",
    ],
    python_requires=">=3.9",
)
