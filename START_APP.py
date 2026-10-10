"""Ga2O3 Thermal Lab launcher — Publisher: RafaelDaSquidman.

Run this file with any existing Python 3.11+ interpreter (Spyder, Anaconda,
Miniconda, VS Code, PyCharm, IDLE, or python.org Python). It never downloads
or installs Python itself.

The launcher creates a private .runtime environment beside the project using
whichever Python interpreter is already running this file. On first launch it
installs only the libraries listed in Python_Code/requirements.txt, then starts
the Streamlit application.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys

PUBLISHER = "RafaelDaSquidman"
MIN_PYTHON = (3, 11)
MAX_TESTED_EXCLUSIVE = (3, 15)

ROOT = Path(__file__).resolve().parent
CODE = ROOT / "Python_Code"
APP = CODE / "app.py"
REQ = CODE / "requirements.txt"
RUNTIME = ROOT / ".runtime"
STAMP = RUNTIME / ".requirements.sha256"
REQUIRED_MODULES = ("numpy", "scipy", "pandas", "plotly", "streamlit", "matplotlib")


def banner() -> None:
    print("=" * 62)
    print("  Ga2O3 Thermal Lab")
    print(f"  Publisher: {PUBLISHER}")
    print("  Existing-Python launcher")
    print("=" * 62)
    print(f"\nUsing Python: {sys.executable}")
    print(f"Version:      {sys.version.split()[0]}")


def pause_if_terminal() -> None:
    # Avoid forcing an input prompt in IDE consoles that may not support it well.
    if os.name == "nt" and sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\nPress Enter to close . . .")
        except (EOFError, KeyboardInterrupt):
            pass


def fail(message: str, code: int = 1) -> "None":
    print(f"\nERROR: {message}")
    pause_if_terminal()
    raise SystemExit(code)


def run_checked(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("\n>", " ".join(f'"{x}"' if " " in str(x) else str(x) for x in cmd))
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)


def runtime_python() -> Path:
    if os.name == "nt":
        return RUNTIME / "Scripts" / "python.exe"
    return RUNTIME / "bin" / "python"


def requirements_hash() -> str:
    return hashlib.sha256(REQ.read_bytes()).hexdigest()


def supports_project() -> bool:
    return MIN_PYTHON <= sys.version_info[:2] < MAX_TESTED_EXCLUSIVE


def verify_project_files() -> None:
    missing = [str(p.relative_to(ROOT)) for p in (APP, REQ) if not p.exists()]
    if missing:
        fail("Required project files are missing: " + ", ".join(missing))


def can_import(python: Path | str) -> bool:
    statement = "; ".join(f"import {name}" for name in REQUIRED_MODULES)
    result = subprocess.run(
        [str(python), "-c", statement],
        cwd=str(CODE),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def prepare_runtime() -> Path:
    """Create/update an isolated environment from the interpreter running us.

    If installation is blocked but the user's current interpreter already has
    every required library, fall back to that interpreter rather than failing.
    """
    if not supports_project():
        fail(
            "This project requires Python 3.11 through 3.14.\n"
            f"The interpreter that opened START_APP.py is Python {sys.version.split()[0]}.\n\n"
            "Open START_APP.py from a compatible Spyder/Anaconda/VS Code/PyCharm "
            "environment, or install a compatible Python separately."
        )

    py = runtime_python()
    wanted = requirements_hash()
    have = STAMP.read_text(encoding="utf-8").strip() if STAMP.exists() else ""

    if py.exists() and wanted == have and can_import(py):
        print("\nPrivate project environment is ready.")
        return py

    print("\nPreparing a private project environment from your existing Python...")
    try:
        if not py.exists():
            run_checked([sys.executable, "-m", "venv", str(RUNTIME)])

        if not py.exists():
            raise RuntimeError("virtual environment was not created")

        run_checked([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQ)])

        if not can_import(py):
            raise RuntimeError("dependency import check failed")

        STAMP.write_text(wanted, encoding="utf-8")
        print("\nProject environment is ready.")
        return py

    except (subprocess.CalledProcessError, OSError, RuntimeError) as exc:
        print(f"\nPrivate environment setup could not finish: {exc}")
        print("Checking whether your current Python environment already has everything needed...")
        if can_import(sys.executable):
            print("All required libraries are already available in your current environment.")
            print("Launching with that interpreter instead.")
            return Path(sys.executable)

        fail(
            "The required Python libraries are not available and could not be installed.\n\n"
            "No Python installation was downloaded or changed by this launcher.\n"
            "If you are using Spyder, keep START_APP.py open there, make sure that "
            "Spyder's Python environment has internet access, and run this file again."
        )


def choose_port(start: int = 8501, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    return start


def launch(python: Path) -> int:
    port = choose_port()
    print("\nStarting Ga2O3 Thermal Lab...")
    print(f"Browser address: http://127.0.0.1:{port}")
    print("Keep this process running while using the app.\n")
    cmd = [
        str(python), "-m", "streamlit", "run", str(APP),
        "--server.address", "127.0.0.1",
        "--server.port", str(port),
        "--server.headless", "false",
        "--browser.gatherUsageStats", "false",
    ]
    try:
        return subprocess.call(cmd, cwd=str(CODE))
    except KeyboardInterrupt:
        print("\nThermal Lab stopped.")
        return 0


def main() -> None:
    banner()
    verify_project_files()

    # Test hook used only for package verification; it makes no changes.
    if os.environ.get("GA2O3_LAUNCHER_TEST") == "1":
        print("\nLauncher self-test mode: project files and current interpreter detected.")
        return

    python = prepare_runtime()
    code = launch(python)
    if code:
        fail(f"Streamlit exited with status {code}.", code)


if __name__ == "__main__":
    main()
