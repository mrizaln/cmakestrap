from importlib import resources as imp_resources
from pathlib import Path

from . import cmake, conan, cpp


class CMake:
    def __init__(self, version: str):
        self.version = version

    def main(self, name: str, std: int, use_main: bool, includes: list[Path]) -> str:
        file = imp_resources.files(cmake) / "main.cmake.in"
        with file.open() as f:
            content = f.read()

        includes_str = ""
        first = True
        for include in includes:
            if not first:
                includes_str += "\n"
            first = False
            includes_str += f"include({include})"

        return content.format(self.version, name, includes_str, std, use_main and "main" or name)

    def module(self, name: str, std: int, use_main: bool, includes: list[Path]) -> str:
        file = imp_resources.files(cmake) / "module.cmake.in"
        with file.open() as f:
            content = f.read()

        includes_str = ""
        first = True
        for include in includes:
            if not first:
                includes_str += "\n"
            first = False
            includes_str += f"include({include})"

        return content.format(self.version, name, includes_str, std, use_main and "main" or name)

    def lib(self, name: str, description: str) -> str:
        file = imp_resources.files(cmake) / "lib.cmake.in"
        with file.open() as f:
            content = f.read()
        return content.format(name, description)

    def prelude(self) -> str:
        file = imp_resources.files(cmake) / "prelude.cmake.in"
        with file.open() as f:
            return f.read()

    def mold(self) -> str:
        file = imp_resources.files(cmake) / "mold.cmake.in"
        with file.open() as f:
            return f.read()

    def fetch(self) -> str:
        file = imp_resources.files(cmake) / "fetch.cmake.in"
        with file.open() as f:
            return f.read()


class Conan:
    def conanfile(self) -> str:
        file = imp_resources.files(conan) / "conanfile.py.in"
        with file.open() as f:
            return f.read()


class Cpp:
    def main(self, name: str) -> str:
        file = imp_resources.files(cpp) / "main.cpp.in"
        with file.open() as f:
            content = f.read()
        return content.format(name)

    def module(self, name: str) -> str:
        # TODO: add module generation, but first create the template
        raise NotImplementedError("Module generation is not implemented yet")

    def lib(self, name: str) -> str:
        file = imp_resources.files(cpp) / "lib.hpp.in"
        with file.open() as f:
            content = f.read()
        return content.format(name)
