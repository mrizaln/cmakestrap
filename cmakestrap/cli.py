import logging
import re
import subprocess
from argparse import ArgumentParser
from collections.abc import Callable
from contextlib import chdir
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from . import templates

BOOTSTRAP_BINARY_DIR = "build/Debug"
BOOTSTRAP_CMD = f"conan install . --build missing -s build_type=Debug \
        && mkdir -p {BOOTSTRAP_BINARY_DIR}/.cmake/api/v1/query \
        && touch {BOOTSTRAP_BINARY_DIR}/.cmake/api/v1/query/codemodel-v2 \
        && cmake --preset conan-debug \
        && ln -s {BOOTSTRAP_BINARY_DIR}/compile_commands.json . \
        && cmake --build --preset conan-debug"

BOOTSTRAP_CMD_MOD = f"conan install . --build missing -s build_type=Debug \
        && mkdir -p {BOOTSTRAP_BINARY_DIR}/.cmake/api/v1/query \
        && touch {BOOTSTRAP_BINARY_DIR}/.cmake/api/v1/query/codemodel-v2 \
        && CXX=clang++ CC=clang cmake --preset conan-debug \
        && ln -s {BOOTSTRAP_BINARY_DIR}/compile_commands.json . \
        && cmake --build --preset conan-debug"

CPP_STD_TO_CMAKE_VER = {
    20: "3.16",
    23: "3.22",
}

PROJECT_NAME_RE: re.Pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


class ProjectKind(Enum):
    LIB = "lib"
    MOD = "mod"
    EXE = "exe"


class Operation(Enum):
    NORMAL_CONFIGURE = "normal_configure"
    CONFIGURE_ONLY = "configure_only"
    BOOTSTRAP_ONLY = "bootstrap_only"
    CMAKE_ONLY = "cmake_only"
    CONAN_ONLY = "conan_only"


@dataclass
class Config:
    dir: Path
    name: str
    cpp_ver: int
    cmake_ver: str
    use_mold: bool
    use_main: bool
    init_git: bool


@dataclass
class Args:
    config: Config
    kind: ProjectKind
    operation: Operation


def get_args() -> Args:
    args = ArgumentParser(description="Simple CMake project initializer")

    add = args.add_argument

    add("dir", help="Directory to initialize")
    add("--name", help="Project name, defaults to directory name if omitted", nargs="?")
    add("--std", help="C++ standard, default: 20", nargs="?", type=int, default=20)
    add("--main", help="Use main as the executable name", action="store_true")

    add("--git", help="Initialize git repository", action="store_true")
    add("--mold", help="Use mold as the linker", action="store_true")
    add("--no-bootstrap", help="Skip bootstrap step", action="store_true")

    kind = args.add_mutually_exclusive_group()
    add = kind.add_argument

    add("--lib", help="Initialize as a library", action="store_true")
    add("--mod", help="Initialize as C++20 module", action="store_true")

    only = args.add_mutually_exclusive_group()
    add = only.add_argument

    add("--bootstrap-only", help="Only run bootstrap step", action="store_true")
    add("--cmake-only", help="Generate CMake files only", action="store_true")
    add("--conan-only", help="Generate Conan files only", action="store_true")

    parsed = args.parse_args()

    dir = Path(parsed.dir).resolve()
    std = parsed.std
    name = parsed.name or dir.name

    if "-" in name:
        logger.warning(f"Project name '{name}' contains dash (-), replacing with underscore (_)")
        name = name.replace("-", "_")
        logger.info(f"Project name changed to '{name}'")

    if not PROJECT_NAME_RE.match(name):
        logger.error(f"Invalid project name: '{name}'")
        logger.error(
            "Project name must start with a letter or underscore and can only contain letters, "
            "digits, and underscores"
        )
        exit(1)

    use_main = parsed.main
    use_mold = parsed.mold
    init_git = parsed.git

    match parsed.lib, parsed.mod:
        case (True, False):
            project_kind = ProjectKind.LIB
        case (False, True):
            project_kind = ProjectKind.MOD
        case _:
            project_kind = ProjectKind.EXE

    if std not in CPP_STD_TO_CMAKE_VER:
        logger.error(f"Invalid C++ version: {std}")
        logger.error(f"Supported versions: {list(CPP_STD_TO_CMAKE_VER.keys())}")
        exit(1)

    if dir.exists() and not dir.is_dir():
        logger.error(f"'{dir}' is not a directory!")
        exit(1)

    if dir.exists() and any(dir.iterdir()):
        response = input(f">>> '{dir}' is not empty, continue? [y/N] ")
        if not response.lower() == "y" and not response.lower() == "yes":
            logger.info("Operation aborted")
            exit(1)

    config = Config(
        dir=dir,
        name=name,
        cpp_ver=std,
        cmake_ver=CPP_STD_TO_CMAKE_VER[std],
        use_mold=use_mold,
        use_main=use_main,
        init_git=init_git,
    )

    should_configure = not (parsed.conan_only or parsed.cmake_only or parsed.bootstrap_only)
    should_bootstrap = not parsed.no_bootstrap and not parsed.lib

    if should_configure and should_bootstrap:
        operation = Operation.NORMAL_CONFIGURE
    elif should_configure:
        operation = Operation.CONFIGURE_ONLY
    elif should_bootstrap:
        operation = Operation.BOOTSTRAP_ONLY
    elif parsed.cmake_only:
        operation = Operation.CMAKE_ONLY
    elif parsed.conan_only:
        operation = Operation.CONAN_ONLY
    else:
        logger.fatal("Invalid operation, how did you get here?")
        exit(1)

    return Args(config=config, kind=project_kind, operation=operation)


def configure_project(cfg: Config, project_kind: ProjectKind) -> bool:
    logger.info(f"Configuring project '{cfg.name}'...")

    configure_path(cfg.dir, project_kind)
    configure_cpp(cfg, project_kind)

    if not configure_cmake(cfg, project_kind):
        logger.error("Failed to configure CMake")
        return False

    if project_kind != ProjectKind.LIB:
        configure_conan(cfg)

    if cfg.init_git:
        configure_git(cfg)

    return True


def configure_path(path: Path, project_kind: ProjectKind):
    logger.info(f"Configuring path '{path}'...")

    if not path.exists():
        path.mkdir()

    if not path.is_dir():
        logger.error(f"'{path}' already exists and is not a directory. Configuration incomplete.")
        return

    match project_kind:
        case ProjectKind.EXE | ProjectKind.MOD:
            source = path / "source"
            source.mkdir(exist_ok=True)

            cmake_include_dir = path / "cmake"
            cmake_include_dir.mkdir(exist_ok=True)

        case ProjectKind.LIB:
            include = path / "include"
            include.mkdir(exist_ok=True)


def configure_cmake(cfg: Config, kind: ProjectKind) -> bool:
    logger.info("Configuring CMake...")

    if (cfg.dir / "CMakeLists.txt").exists():
        logger.error(f"'{cfg.dir}' already contains a CMakeLists.txt file")
        return False

    cmake_dir = cfg.dir / "cmake"
    assert cmake_dir.exists(), "CMake directory does not exist"

    tmpl = templates.CMake(cfg.cmake_ver)
    includes: list[Path] = []

    if kind == ProjectKind.LIB:
        cmake_main = cfg.dir / "CMakeLists.txt"
        write_tmpl(cmake_main, tmpl.lib, cfg.name, f"<{cfg.name} library description>")
        return True

    # in-place build guard
    cmake_guard = cmake_dir / "prelude.cmake"
    if write_tmpl(cmake_guard, tmpl.prelude):
        includes.append(cmake_guard.relative_to(cfg.dir))

    # mold include
    cmake_mold = cmake_dir / "mold.cmake"
    if cfg.use_mold:
        if write_tmpl(cmake_mold, tmpl.mold):
            includes.append(cmake_mold.relative_to(cfg.dir))

    # main cmake file
    cmake_main = cfg.dir / "CMakeLists.txt"
    match kind:
        case ProjectKind.EXE:
            write_tmpl(cmake_main, tmpl.main, cfg.name, cfg.cpp_ver, cfg.use_main, includes)
        case ProjectKind.MOD:
            write_tmpl(cmake_main, tmpl.module, cfg.name, cfg.cpp_ver, cfg.use_main, includes)

    # fetchcontent
    cmake_fetch = cmake_dir / "fetched-libs.cmake"
    write_tmpl(cmake_fetch, tmpl.fetch)

    return True


def configure_conan(cfg: Config):
    logger.info("Configuring Conan...")

    conanfile = cfg.dir / "conanfile.py"
    tmpl = templates.Conan()
    write_tmpl(conanfile, tmpl.conanfile)


def configure_cpp(cfg: Config, project_kind: ProjectKind):
    logger.info("Configuring C++ files...")

    source = cfg.dir / "source"
    include = cfg.dir / "include"

    if project_kind == ProjectKind.LIB:
        assert include.exists(), "Include directory does not exist"
    else:
        assert source.exists(), "Source directory does not exist"

    tmpl = templates.Cpp()

    match project_kind:
        case ProjectKind.EXE:
            lib = source / f"{cfg.name}.hpp"
            write_tmpl(lib, tmpl.lib, cfg.name)
            main = source / "main.cpp"
            write_tmpl(main, tmpl.main, cfg.name)
        case ProjectKind.MOD:
            main = source / "main.cxx"
            write_tmpl(main, tmpl.module, cfg.name)
        case ProjectKind.LIB:
            lib = include / f"{cfg.name}.hpp"
            write_tmpl(lib, tmpl.lib, cfg.name)


def configure_git(cfg: Config):
    logger.info("Configuring git...")

    try:
        with chdir(cfg.dir):
            subprocess.run(["git", "init"]).check_returncode()
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to initialize git: {e}")

    gitignore = cfg.dir / ".gitignore"
    # TODO: write gitignore template, but first create the template for it


def write_tmpl[**P](file: Path, tmpl_fn: Callable[P, str], *a: P.args, **k: P.kwargs) -> bool:
    if not file.exists():
        file.write_text(tmpl_fn(*a, **k))
        return True
    else:
        logger.warning(f"'{file}' already exists, skipping")
        return False


def bootstrap_project(cfg: Config, modules: bool) -> Path | None:
    cmake = cfg.dir / "CMakeLists.txt"
    if not cmake.exists():
        logger.error("CMakeLists.txt does not exist, cannot bootstrap")
        return None

    with chdir(cfg.dir):
        command = BOOTSTRAP_CMD_MOD if modules else BOOTSTRAP_CMD
        command = " ".join(command.split())  # remove repeated spaces
        completed_process = subprocess.run(command, shell=True)
        try:
            completed_process.check_returncode()
            logger.info("Bootstrap complete.")
        except subprocess.CalledProcessError as e:
            logger.error(f"\nFailed to bootstrap: \n{e}")
            return None

        return cfg.dir / BOOTSTRAP_BINARY_DIR / "main"


def main() -> int:
    args = get_args()

    match args.operation:
        case Operation.NORMAL_CONFIGURE:
            success = configure_project(args.config, args.kind)
            if success:
                bootstrap_project(args.config, args.kind == ProjectKind.MOD)
            logger.info("Project configured successfully")
        case Operation.CONFIGURE_ONLY:
            configure_project(args.config, args.kind)
            logger.info("Project configured successfully")
        case Operation.BOOTSTRAP_ONLY:
            bootstrap_project(args.config, args.kind == ProjectKind.MOD)
        case Operation.CMAKE_ONLY:
            configure_path(args.config.dir, args.kind)
            configure_cmake(args.config, args.kind)
        case Operation.CONAN_ONLY:
            configure_conan(args.config)

    return 0
