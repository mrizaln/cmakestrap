import logging
import os
import platform
import pprint
import re
import sys
from argparse import ArgumentParser
from collections.abc import Callable
from contextlib import chdir
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from subprocess import DEVNULL, CalledProcessError, run

from . import templates
from .__version__ import __version__

IS_WINDOWS = platform.system() == "Windows"

# fmt: off
BOOTSTRAP_BINARY_DIR   = "build/Debug"
BOOTSTRAP_INSTALL      = "conan install . --build missing -s build_type=Debug"
BOOTSTRAP_GENERATE     = "cmake --preset conan-debug"
BOOTSTRAP_GENERATE_NT  = "cmake --preset conan-default"
BOOTSTRAP_LINK_COMP_DB = f"ln -sf {BOOTSTRAP_BINARY_DIR}/compile_commands.json ."
BOOTSTRAP_COMPILE      = "cmake --build --preset conan-debug"
# fmt: on

CPP_STD_TO_CMAKE_VER = {
    20: "3.16",
    23: "3.22",
}

CMAKE_VER_WITH_MODULES = "3.28"

PROJECT_NAME_RE: re.Pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


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


class Log(Enum):
    QUIET = "quiet"
    DEBUG = "debug"
    NORMAL = "normal"
    VERBOSE = "verbose"


@dataclass
class Config:
    dir: Path
    name: str
    cpp_ver: int
    cmake_ver: str
    use_mold: bool
    use_main: bool
    init_git: bool
    log: Log


@dataclass
class Args:
    config: Config
    kind: ProjectKind
    operation: Operation


class CustomFormatter(logging.Formatter):
    BLUE = "\x1b[34;20m"
    GREEN = "\x1b[32;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"
    FMT = "%(asctime)s [{}-%(levelname).1s-{}] %(message)s"

    FORMATS = {
        logging.DEBUG: FMT.format(BLUE, RESET),
        logging.INFO: FMT.format(GREEN, RESET),
        logging.WARNING: FMT.format(YELLOW, RESET),
        logging.ERROR: FMT.format(RED, RESET),
        logging.CRITICAL: FMT.format(BOLD_RED, RESET),
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(fmt=log_fmt, datefmt="[%Y-%m-%d|%H:%M:%S]")
        return formatter.format(record)


logger = logging.getLogger(__name__)


def init_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(CustomFormatter())
    logger.addHandler(ch)


def get_args() -> Args:
    if not command_exists("cmake"):
        logger.fatal("CMake is not installed, please install it first")
        exit(1)

    if not command_exists("conan"):
        logger.fatal("This script use Conan as dependency manager, please install it first")
        exit(1)

    args = ArgumentParser(description="Simple CMake project initializer")

    add = args.add_argument

    add("dir", help="Directory to initialize (can be empty or non-existent)")
    add("--name", help="Project name, defaults to directory name if omitted")
    add("--std", help="C++ standard to be used, default: 20", type=int, default=20)
    add("--main", help="Use main as the executable name (exe/mod mode)", action="store_true")

    kind = args.add_mutually_exclusive_group()
    add = kind.add_argument

    add("--exe", help="Initialize project as executable (default)", action="store_true")
    add("--mod", help="Initialize project as executable using C++20 modules", action="store_true")
    add("--lib", help="Initialize project as library", action="store_true")

    add = args.add_argument

    add("--git", help="Initialize git", action="store_true")
    add("--mold", help="Use mold as the linker", action="store_true")
    add("--no-bootstrap", help="Skip bootstrap step", action="store_true")

    only = args.add_mutually_exclusive_group()
    add = only.add_argument

    add("--bootstrap-only", help="Only run bootstrap step", action="store_true")
    add("--cmake-only", help="Generate CMake files only", action="store_true")
    add("--conan-only", help="Generate Conan files only", action="store_true")

    log_level = args.add_mutually_exclusive_group()
    add = log_level.add_argument

    add("--debug", help="Enable debug logging", action="store_true")
    add("--quiet", help="Enable quiet logging", action="store_true")
    add("--verbose", help="Enable verbose logging", action="store_true")

    args.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    if len(sys.argv) == 1:
        args.print_help()
        exit(1)

    parsed = args.parse_args()

    match parsed.debug, parsed.quiet, parsed.verbose:
        case True, False, False:
            cmd_output = Log.DEBUG
            logger.setLevel(logging.DEBUG)
        case False, True, False:
            cmd_output = Log.QUIET
            logger.setLevel(logging.WARNING)
        case False, False, True:
            cmd_output = Log.VERBOSE
            logger.setLevel(logging.INFO)
        case _:
            cmd_output = Log.NORMAL
            logger.setLevel(logging.INFO)

    dir = Path(parsed.dir).resolve()
    std = parsed.std
    name = parsed.name or dir.name

    if "-" in name:
        logger.warning(f"Project name '{name}' contains hyphen (-), replacing with underscore (_)")
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

    if project_kind == ProjectKind.MOD and not command_exists("clang++"):
        logger.fatal("clang++ executable not found")
        logger.fatal("This script only support clang for C++20 modules at the moment")
        exit(1)

    if std not in CPP_STD_TO_CMAKE_VER:
        logger.error(f"Invalid C++ version: {std}")
        logger.error(f"Supported versions: {list(CPP_STD_TO_CMAKE_VER.keys())}")
        exit(1)

    if dir.exists() and not dir.is_dir():
        logger.error(f"'{dir}' is not a directory!")
        exit(1)

    if dir.exists() and any(dir.iterdir()) and not parsed.bootstrap_only:
        response = input(f">>> '{dir}' is not empty, continue? [y/N] ")
        if not response.lower() == "y" and not response.lower() == "yes":
            logger.info("Operation aborted")
            exit(1)

    cmake_ver = (
        CPP_STD_TO_CMAKE_VER[std] if project_kind != ProjectKind.MOD else CMAKE_VER_WITH_MODULES
    )

    config = Config(
        dir=dir,
        name=name,
        cpp_ver=std,
        cmake_ver=cmake_ver,
        use_mold=use_mold,
        use_main=use_main,
        init_git=init_git,
        log=cmd_output,
    )

    should_configure = not (parsed.conan_only or parsed.cmake_only or parsed.bootstrap_only)
    should_bootstrap = not parsed.no_bootstrap and not parsed.lib

    if should_configure and should_bootstrap:
        operation = Operation.NORMAL_CONFIGURE
    elif should_configure:
        operation = Operation.CONFIGURE_ONLY
    elif parsed.cmake_only:
        operation = Operation.CMAKE_ONLY
    elif parsed.conan_only:
        operation = Operation.CONAN_ONLY
    elif should_bootstrap:
        operation = Operation.BOOTSTRAP_ONLY
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
            source = path / "src"
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

    tmpl = templates.CMake(cfg.cmake_ver)

    if kind == ProjectKind.LIB:
        cmake_main = cfg.dir / "CMakeLists.txt"
        write_tmpl(cmake_main, tmpl.lib, cfg.name, f"<{cfg.name} library description>")
        return True

    cmake_dir = cfg.dir / "cmake"
    assert cmake_dir.exists(), "CMake directory does not exist"

    includes: list[Path] = []

    # in-place build guard
    cmake_guard = cmake_dir / "prelude.cmake"
    if write_tmpl(cmake_guard, tmpl.prelude):
        includes.append(cmake_guard.relative_to(cfg.dir))

    # mold include
    cmake_mold = cmake_dir / "mold.cmake"
    if cfg.use_mold:
        if command_exists("mold"):
            if write_tmpl(cmake_mold, tmpl.mold):
                includes.append(cmake_mold.relative_to(cfg.dir))
        else:
            logger.warning("Mold executable not found, skipping mold configuration")

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

    source = cfg.dir / "src"
    include = cfg.dir / "include"

    if project_kind == ProjectKind.LIB:
        assert include.exists(), "Include directory does not exist"
    else:
        assert source.exists(), "Source directory does not exist"

    tmpl = templates.Cpp()

    match project_kind:
        case ProjectKind.EXE:
            lib = source / f"{cfg.name}.hpp"
            write_tmpl(lib, tmpl.lib, cfg.name, True)
            main = source / "main.cpp"
            write_tmpl(main, tmpl.main, cfg.name)
        case ProjectKind.MOD:
            lib = source / f"{cfg.name}.cxx"
            write_tmpl(lib, tmpl.lib_mod, cfg.name)
            main = source / "main.cxx"
            write_tmpl(main, tmpl.main_mod, cfg.name)
        case ProjectKind.LIB:
            lib = include / f"{cfg.name}.hpp"
            write_tmpl(lib, tmpl.lib, cfg.name, False)


def configure_git(cfg: Config):
    if not command_exists("git"):
        logger.warning("Git executable not found, skipping git configuration")
        return

    logger.info("Configuring git...")

    try:
        with chdir(cfg.dir):
            run(["git", "init"], capture_output=cfg.log in [Log.QUIET, Log.NORMAL], check=True)
    except CalledProcessError as e:
        logger.error(f"Last command stderr: \n{e.stderr.decode()}")
        logger.error(f"Failed to initialize git: \n{e}")

    gitignore = cfg.dir / ".gitignore"
    tmpl = templates.Git()
    write_tmpl(gitignore, tmpl.gitignore)


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

    logger.info(f"Bootstrapping project '{cfg.name}'...")

    install = BOOTSTRAP_INSTALL.split()
    generate = (BOOTSTRAP_GENERATE_NT if IS_WINDOWS else BOOTSTRAP_GENERATE).split()
    link_comp_db = BOOTSTRAP_LINK_COMP_DB.split()
    compile = BOOTSTRAP_COMPILE.split()

    commands = (install, generate, link_comp_db, compile)

    with chdir(cfg.dir):
        for cmd in commands:
            try:
                env = os.environ | ({"CXX": "clang++", "CC": "clang"} if modules else {})
                run(cmd, env=env, capture_output=cfg.log in [Log.QUIET, Log.NORMAL], check=True)
            except CalledProcessError as e:
                logger.error(f"Last command stdout: \n{e.stdout.decode() if not None else ''}")
                logger.error(f"Last command stderr: \n{e.stderr.decode() if not None else ''}")
                logger.error(f"Failed to bootstrap: \n{e}")
                return None

        logger.info("Bootstrap complete")
        return cfg.dir / BOOTSTRAP_BINARY_DIR / ("main" if cfg.use_main else cfg.name)


def command_exists(command: str) -> bool:
    cmd = "where" if platform.system() == "Windows" else "which"
    try:
        run([cmd, command], stdout=DEVNULL, stderr=DEVNULL, check=True)
        return True
    except CalledProcessError:
        return False


def main() -> int:
    init_logger()

    args = get_args()

    args_str = pprint.pformat(asdict(args), sort_dicts=False)
    logger.debug(f"Parsed arguments:\n{args_str}")

    match args.operation:
        case Operation.NORMAL_CONFIGURE:
            if configure_project(args.config, args.kind):
                if exe := bootstrap_project(args.config, args.kind == ProjectKind.MOD):
                    logger.info("Project configured successfully")
                    run(exe, check=True, capture_output=args.config.log == Log.QUIET)
        case Operation.CONFIGURE_ONLY:
            configure_project(args.config, args.kind)
            logger.info("Project configured successfully")
        case Operation.BOOTSTRAP_ONLY:
            if exe := bootstrap_project(args.config, args.kind == ProjectKind.MOD):
                run(exe, check=True, capture_output=args.config.log == Log.QUIET)
        case Operation.CMAKE_ONLY:
            configure_path(args.config.dir, args.kind)
            configure_cmake(args.config, args.kind)
        case Operation.CONAN_ONLY:
            configure_path(args.config.dir, args.kind)
            configure_conan(args.config)

    return 0
