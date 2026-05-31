from importlib import resources as imp_resources
from pathlib import Path
from string import Template

from . import cmake, conan, cpp, git


class CMake:
    def __init__(self, version: str):
        self.version = version

    def main(
        self,
        name_original: str,
        name_safe: str,
        std: int,
        use_main: bool,
        includes: list[Path],
        description: str,
    ) -> str:
        file = imp_resources.files(cmake) / "main.cmake.in"
        with file.open() as f:
            template = Template(f.read())
            mapping = {
                "cmake_version": self.version,
                "project_name": name_original,
                "project_name_safe": name_safe,
                "executable_name": use_main and "main" or name_original,
                "cpp_standard": std,
                "description": description,
                "includes": "\n".join(f"include({include})" for include in includes),
            }
            return template.substitute(mapping)

    def module(
        self,
        name_original: str,
        name_safe: str,
        std: int,
        use_main: bool,
        includes: list[Path],
        description: str,
    ) -> str:
        file = imp_resources.files(cmake) / "module.cmake.in"
        with file.open() as f:
            template = Template(f.read())
            mapping = {
                "cmake_version": self.version,
                "project_name": name_original,
                "project_name_safe": name_safe,
                "executable_name": use_main and "main" or name_original,
                "cpp_standard": std,
                "description": description,
                "includes": "\n".join(f"include({include})" for include in includes),
            }
            return template.substitute(mapping)

    def lib(self, name_original: str, name_safe: str, std: int, description: str) -> str:
        file = imp_resources.files(cmake) / "lib.cmake.in"
        with file.open() as f:
            template = Template(f.read())
            mapping = {
                "cmake_version": self.version,
                "project_name": name_original,
                "project_name_safe": name_safe,
                "cpp_standard": std,
                "description": description,
            }
            return template.substitute(mapping)

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
    def conanfile(self, fmt_version: str) -> str:
        file = imp_resources.files(conan) / "conanfile.py.in"
        with file.open() as f:
            template = Template(f.read())
            return template.substitute({"fmt_version": fmt_version})


class Cpp:
    def main(self, name_safe: str) -> str:
        file = imp_resources.files(cpp) / "main.cpp.in"
        with file.open() as f:
            template = Template(f.read())
            return template.substitute({"project_name_safe": name_safe})

    def lib_hpp(self, name_safe: str) -> str:
        file = imp_resources.files(cpp) / "lib.hpp.in"
        with file.open() as f:
            template = Template(f.read())
            return template.substitute({"project_name_safe": name_safe})

    def lib_cpp(self, name_original: str, name_safe: str, use_fmt: bool) -> str:
        file = imp_resources.files(cpp) / ("lib.cpp.in" if use_fmt else "lib-no-fmt.cpp.in")
        with file.open() as f:
            template = Template(f.read())
            mapping = {
                "project_name": name_original,
                "project_name_safe": name_safe,
            }
            return template.substitute(mapping)

    def main_mod(self, name_safe: str) -> str:
        file = imp_resources.files(cpp) / "main.cxx.in"
        with file.open() as f:
            template = Template(f.read())
            return template.substitute({"project_name_safe": name_safe})

    def lib_mod(self, name_original: str, name_safe) -> str:
        file = imp_resources.files(cpp) / "lib.cxx.in"
        with file.open() as f:
            template = Template(f.read())
            mapping = {
                "project_name": name_original,
                "project_name_safe": name_safe,
            }
            return template.substitute(mapping)


class Git:
    def gitignore(self) -> str:
        file = imp_resources.files(git) / ".gitignore.in"
        with file.open() as f:
            return f.read()
