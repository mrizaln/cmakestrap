# cmakestrap

Simpler CMake project initializer script for C++ (with Conan).

## Motivation

There is no C++ with CMake project initializer script in the wild except for [cmake-init](https://github.com/friendlyanon/cmake-init).
Unfortunately, the generated files from it are too much for my liking. Looking at this [issue](https://github.com/friendlyanon/cmake-init/issues/75), that has been up for 2 years, it seems that the author is not interested in providing an option to generate a simpler, thinner, project structure. This script is an attempt to provide that.

## Installation

cmakestrap is available from [PyPI](https://pypi.org/project/cmakestrap/):

```
pip install --user cmakestrap
```

## Dependencies

- Python 3.12+
- CMake 3.16+ (might need higher version for newer C++ features)
- Conan 2 (for dependency management)

## Features

This script provides a simple way to bootstrap a C++ project with CMake (build system) and Conan (dependency management). You can generate projects in 3 mode:

- Executable mode (default): generate a traditional C++ project structure with headers and such.
- Library mode: generate a header only library project (C++20).
- Modules mode: generate a CMake module project (requires CMake 3.28+ and supported compilers).

> Initializing a simple hello world project:

```
cmakestrap hello
```

> To see the available options, run the script with the `-h` flag:

```
cmakestrap -h
```
