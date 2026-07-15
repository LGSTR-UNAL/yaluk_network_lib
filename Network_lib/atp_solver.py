from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from .utils import get_short_path

ATP_RUNTIME_FILES = (
    "startup",
    "startup.big",
    "startup.gig",
    "graphics",
    "graphics.aux",
    "graphics.std",
    "blockd51.bin",
    "Atp_Yaluk_lib.dll",
)


def resolve_solver_executable(solver_path: str | os.PathLike | None = None) -> Path:
    if solver_path is not None:
        return Path(solver_path)

    if "SOLVER_PATH" in os.environ:
        return Path(os.environ["SOLVER_PATH"])

    if platform.system() == "Windows":
        default_windows_solver = Path(r"C:\EMTP\Solver\tp_yaluk.exe")
        if default_windows_solver.exists():
            return default_windows_solver

    candidates = ("tp_yaluk.exe",) if platform.system() == "Windows" else ("tpyaluk",)
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return Path(found)

    return Path(candidates[0])


def run_atp_solver(
    input_file: str | os.PathLike,
    solver_path: str | os.PathLike | None = None,
    solver_cwd: str | os.PathLike | None = None,
    mode: str = "BOTH",
    switches: tuple[str, ...] = ("s", "-r"),
):
    executable = resolve_solver_executable(solver_path)
    input_file = Path(input_file).resolve()
    executable_parent = (
        executable.resolve().parent
        if executable.exists()
        else executable.parent.resolve()
    )
    cwd = Path(solver_cwd).resolve() if solver_cwd is not None else input_file.parent
    if os.name == "nt" and cwd == executable_parent:
        cwd = input_file.parent
    input_arg = (
        input_file.name
        if input_file.parent == cwd
        else get_short_path(input_file) if os.name == "nt" else str(input_file)
    )

    if not executable.exists() and shutil.which(str(executable)) is None:
        raise FileNotFoundError(
            f"Could not find ATP/Yaluk solver executable: {executable}. "
            "Pass solver_path explicitly, for example "
            r"solver_path='C:\EMTP\Solver\tp_yaluk.exe'."
        )
    if not cwd.exists():
        raise FileNotFoundError(f"Solver working directory does not exist: {cwd}")

    env = None
    if os.name == "nt":
        env = os.environ.copy()
        solver_dir = str(executable_parent) + os.sep
        env.setdefault("ATPDIR", solver_dir)
        env.setdefault("GNUDIR", solver_dir)

    if cwd != executable_parent:
        for runtime_file in ATP_RUNTIME_FILES:
            source = executable_parent / runtime_file
            target = cwd / runtime_file
            if source.exists() and not target.exists():
                shutil.copy2(source, target)

    command = [str(executable), mode, input_arg, *switches]
    print(f"Running command: {' '.join(command)}")
    try:
        return subprocess.run(
            command,
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        lis_candidates = [
            input_file.with_suffix(".lis"),
            cwd / input_file.with_suffix(".lis").name,
        ]
        lis_text = ""
        for lis_file in lis_candidates:
            if lis_file.exists():
                lis_text = lis_file.read_text(errors="replace")[-4000:]
                break
        details = [
            f"ATP/Yaluk solver failed with exit code {exc.returncode}.",
            f"Command: {' '.join(command)}",
        ]
        if exc.stdout:
            details.append(f"stdout:\n{exc.stdout[-4000:]}")
        if exc.stderr:
            details.append(f"stderr:\n{exc.stderr[-4000:]}")
        if lis_text:
            details.append(f"LIS tail:\n{lis_text}")
        raise RuntimeError("\n\n".join(details)) from exc


def cleanup_solver_files(
    directory: str | os.PathLike,
    patterns: tuple[str, ...] = ("*.pl4", "*.tmp", "*.gnu", "*.dbg"),
) -> None:
    directory = Path(directory)
    for pattern in patterns:
        for file in directory.glob(pattern):
            if file.is_file():
                file.unlink()


def run_atp_file(
    atp_file: str | os.PathLike,
    solver_path: str | os.PathLike | None = None,
    solver_cwd: str | os.PathLike | None = None,
    keep_pl4: bool = True,
    check_lis: bool = True,
):
    """Run an ATP .atp file and optionally keep the generated .pl4 output."""
    atp_file = Path(atp_file)
    if atp_file.suffix.lower() != ".atp":
        raise ValueError(f"Expected an .atp file, got: {atp_file}")

    result = run_atp_solver(
        atp_file,
        solver_path=solver_path,
        solver_cwd=solver_cwd,
        mode="BOTH",
        switches=("s", "-r"),
    )

    if check_lis:
        check_required_output(atp_file.with_suffix(".lis"), "ATP listing")

    cleanup_patterns = ("*.tmp", "*.gnu", "*.dbg")
    if not keep_pl4:
        cleanup_patterns = ("*.pl4", *cleanup_patterns)
    cleanup_solver_files(atp_file.resolve().parent, cleanup_patterns)

    return result


def check_required_output(file: str | os.PathLike, label: str) -> None:
    file = Path(file)
    if not file.exists():
        raise FileNotFoundError(f"Expected {label} file was not created: {file}")
    if file.stat().st_size == 0:
        raise RuntimeError(f"Expected {label} file is empty: {file}")
