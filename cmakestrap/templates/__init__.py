from importlib import resources as imp_resources
from pathlib import Path

from . import cmake, conan, cpp, git


class CMake:
    def __init__(self, version: str):
        self.version = version

    def main(
        self,
        name: str,
        orig_name: str,
        std: int,
        use_main: bool,
        includes: list[Path],
        description: str,
    ) -> str:
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

        return content.format(
            self.version,
            name,
            orig_name,
            includes_str,
            std,
            use_main and "main" or orig_name,
            description,
        )

    def module(
        self,
        name: str,
        orig_name: str,
        std: int,
        use_main: bool,
        includes: list[Path],
        description: str,
    ) -> str:
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

        return content.format(
            self.version,
            name,
            orig_name,
            includes_str,
            std,
            use_main and "main" or orig_name,
            description,
        )

    def lib(self, name: str, orig_name: str, std: int, description: str) -> str:
        file = imp_resources.files(cmake) / "lib.cmake.in"
        with file.open() as f:
            content = f.read()
        return content.format(self.version, name, orig_name, std, description)

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

    def lib_hpp(self, name: str) -> str:
        file = imp_resources.files(cpp) / "lib.hpp.in"
        with file.open() as f:
            content = f.read()
        return content.format(name)

    def lib_cpp(self, name: str, orig_name: str, use_fmt: bool) -> str:
        file = imp_resources.files(cpp) / ("lib.cpp.in" if use_fmt else "lib-no-fmt.cpp.in")
        with file.open() as f:
            content = f.read()
        return content.format(name, orig_name)

    def main_mod(self, name: str) -> str:
        file = imp_resources.files(cpp) / "main.cxx.in"
        with file.open() as f:
            content = f.read()
        return content.format(name)

    def lib_mod(self, name: str, orig_name) -> str:
        file = imp_resources.files(cpp) / "lib.cxx.in"
        with file.open() as f:
            content = f.read()
        return content.format(name, orig_name)


class Git:
    def gitignore(self) -> str:
        file = imp_resources.files(git) / ".gitignore.in"
        with file.open() as f:
            return f.read()
