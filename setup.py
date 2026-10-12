"""
MARK LIV — one-time setup.

Installs the Python dependencies for THIS operating system only: the OS-specific
packages in requirements.txt carry `sys_platform` markers, so a macOS or Linux
user never pulls Windows-only libraries (and vice-versa). Then it fetches the
Playwright browsers needed for web automation (current-OS builds only).

Where to install is autodetected. If this interpreter already accepts pip
(Windows, a conda/venv you activated, a user-built Python), packages go there.
If it is marked EXTERNALLY-MANAGED — Debian, Ubuntu, Fedora, Homebrew, PEP 668
— setup creates a project-local `.venv` and continues inside it. `python main.py`
follows the same rule, so the launch command does not change.

Two things it deliberately does NOT install:
  * the optional local wake word ("Hey Jarvis") — one-click, opt-in, from
    ⚙ → WAKE WORD inside the app;
  * anything for the avatar — the holographic head renders in software on the
    PyQt6 and numpy already listed here. No GPU, no OpenGL, no extra packages.
"""
import os
import platform
import subprocess
import sys
import sysconfig
from pathlib import Path

OS = platform.system()  # "Windows" | "Darwin" | "Linux"
HERE = Path(__file__).resolve().parent
VENV_DIR = HERE / ".venv"

MIN_PY = (3, 11)        # hard floor: below this the syntax used here won't parse
MAX_PY = (3, 13)        # highest version this is actually tested on


def _run(label: str, args: list[str]) -> None:
    print(f"\n▶ {label}")
    subprocess.run(args, check=True)


def _pep668_pip_error(_exc: BaseException) -> bool:
    """True if a failed pip run was the PEP 668 lock, not a real package error.

    Used only as a fallback when the EXTERNALLY-MANAGED marker is absent but
    pip still refuses. We re-run pip capturing stderr — the first attempt
    already printed the error, so the user sees it once.
    """
    # CalledProcessError from the first run has no captured output (we stream
    # it live). Probe with a no-op install so we can read the message.
    probe = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--dry-run", "pip"],
        capture_output=True, text=True,
    )
    blob = (probe.stderr or "") + (probe.stdout or "")
    return "externally-managed-environment" in blob or "EXTERNALLY-MANAGED" in blob


def _in_venv() -> bool:
    return (
        getattr(sys, "base_prefix", sys.prefix) != sys.prefix
        or bool(os.environ.get("VIRTUAL_ENV"))
    )


def _externally_managed() -> bool:
    """True when this interpreter is PEP 668-locked (pip will refuse it).

    Honour PIP_BREAK_SYSTEM_PACKAGES: if the user already opted out of the
    lock, installing into this interpreter is what they asked for.
    """
    flag = os.environ.get("PIP_BREAK_SYSTEM_PACKAGES", "").strip().lower()
    if flag in ("1", "true", "yes"):
        return False
    try:
        return (Path(sysconfig.get_path("stdlib")) / "EXTERNALLY-MANAGED").is_file()
    except Exception:
        return False


def _needs_venv() -> bool:
    return (not _in_venv()) and _externally_managed()


def _venv_python() -> Path:
    if OS == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _exec_in(python: Path) -> None:
    """Replace this process with `python setup.py`, same arguments."""
    argv = [str(python), str(HERE / "setup.py"), *sys.argv[1:]]
    try:
        os.execv(argv[0], argv)
    except OSError:
        raise SystemExit(subprocess.run(argv).returncode)


def _ensure_venv() -> Path:
    """Create `.venv` if needed and return the interpreter inside it."""
    python = _venv_python()
    if python.exists():
        return python

    print(f"\n▶ Creating virtual environment at {VENV_DIR}…")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\n❌ Could not create a virtual environment.")
        print("   Debian / Ubuntu:  sudo apt install python3-venv python3-full")
        print("   Fedora:           sudo dnf install python3")
        print("   Then re-run:      python3 setup.py")
        sys.exit(1)

    python = _venv_python()
    if not python.exists():
        print(f"\n❌ venv was created but {python} is missing.")
        sys.exit(1)

    # Some distro venvs ship without pip. ensurepip fills that gap.
    probe = subprocess.run(
        [str(python), "-m", "pip", "--version"], capture_output=True
    )
    if probe.returncode != 0:
        subprocess.run(
            [str(python), "-m", "ensurepip", "--upgrade"], check=True
        )
    return python


def _check_python() -> None:
    """Fail immediately and clearly rather than deep inside a pip resolver.

    A wrong interpreter is the single most common way this install goes sideways,
    and the error it produces on its own names a wheel, not the real problem.
    """
    v = sys.version_info[:2]
    if v > MAX_PY:
        # Newer is a warning, not a wall. Turning away someone who installed
        # today's Python is a worse first impression than a version that
        # turns out to work fine, and if a wheel really is missing pip says
        # so plainly.
        print(f"\n⚠️  Python {v[0]}.{v[1]} is newer than the "
              f"{MAX_PY[0]}.{MAX_PY[1]} this is tested on. Continuing — if a "
              f"package has no wheel yet, install Python "
              f"{MAX_PY[0]}.{MAX_PY[1]} and run setup with that.")
        return
    if v < MIN_PY:
        print(f"\n❌ Python {v[0]}.{v[1]} detected — MARK LIV needs at "
              f"least Python {MIN_PY[0]}.{MIN_PY[1]}.")
        print("   Install a supported version and run setup with it, e.g.:")
        print(f"     py -{MIN_PY[0]}.{MIN_PY[1]} setup.py        (Windows)")
        print(f"     python{MIN_PY[0]}.{MIN_PY[1]} setup.py      (macOS / Linux)")
        sys.exit(1)


def _check_assets() -> None:
    """The avatar's face is a shipped file; a truncated clone should say so."""
    face = HERE / "core" / "face_model.obj"
    if not face.exists() or face.stat().st_size < 4096:
        print(
            "\n⚠️  core/face_model.obj is missing or truncated — the avatar will "
            "fall back to the plain glowing core.\n"
            "    Re-clone the repository, or fetch that one file again."
        )


def main() -> None:
    print(f"⚙  MARK LIV setup — detected OS: {OS or 'unknown'}, "
          f"Python {sys.version_info[0]}.{sys.version_info[1]}")
    _check_python()

    # Autodetect the install target. PEP 668 (EXTERNALLY-MANAGED) is the
    # signal that pip into this interpreter will fail; everything else —
    # Windows, conda, an already-activated venv — just installs here.
    if _needs_venv():
        venv_py = _ensure_venv()
        print("\n▶ System Python is externally managed (PEP 668) — "
              "installing into a project .venv")
        print(f"▶ Re-running setup inside {venv_py}…")
        _exec_in(venv_py)

    # requirements.txt filters OS-specific extras by itself via pip markers.
    try:
        _run("Installing Python dependencies (OS-specific extras auto-filtered)…",
             [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    except subprocess.CalledProcessError as e:
        # Marker file missing on some distros; pip's own error is the fallback.
        if not _in_venv() and _pep668_pip_error(e):
            venv_py = _ensure_venv()
            print("\n▶ pip refused a system install — retrying inside a venv…")
            print(f"▶ Re-running setup inside {venv_py}…")
            _exec_in(venv_py)
        raise

    # Chromium covers Chrome/Edge/Opera/Brave/Vivaldi; Firefox for Firefox.
    # (Safari automation additionally needs: python -m playwright install webkit)
    # Not fatal: these are a few hundred megabytes from a CDN that a corporate
    # network or a flaky connection can refuse, and everything except browser
    # automation works without them. Failing the whole install there would send
    # a user away from a working app.
    try:
        _run("Installing Playwright browsers (chromium + firefox)…",
             [sys.executable, "-m", "playwright", "install", "chromium", "firefox"])
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"\n⚠️  Playwright browsers were not installed ({e}).")
        print("    Everything except browser automation works. Retry later with:")
        print(f'    {sys.executable} -m playwright install chromium firefox')

    _check_assets()

    # ── OS-specific post-install notes ────────────────────────────────────────
    if OS == "Windows":
        try:
            import win32com.client  # noqa: F401
        except ImportError:
            postinstall = Path(sys.executable).parent / "Scripts" / "pywin32_postinstall.py"
            print(
                "\n⚠️  pywin32 did not register correctly — desktop-shortcut "
                "creation will use a slower fallback. To fix it, run:\n"
                f'    "{sys.executable}" -m pip install --force-reinstall pywin32\n'
                f'    "{sys.executable}" "{postinstall}" -install'
            )
    elif OS == "Linux":
        print(
            "\nℹ️  Linux note — a few voice-controlled OS actions shell out to "
            "native tools. Install the ones you'll use via your package manager:\n"
            "    • volume      → pulseaudio-utils   (pactl)\n"
            "    • brightness  → brightnessctl\n"
            "    • reminders   → systemd (systemd-run) or 'at'\n"
            "    • open URLs   → xdg-utils          (xdg-open)"
        )
    elif OS == "Darwin":
        print(
            "\nℹ️  macOS note — volume, brightness and reminders use the built-in "
            "'osascript' / LaunchAgents, so no extra tools are required.\n"
            "    For Safari automation only: python -m playwright install webkit"
        )

    print("\n✅ Setup complete!")
    print("   1) Launch it:  python main.py")
    if _in_venv():
        print(f"      (using {sys.executable})")
    print("   2) Paste your free Gemini API key when the setup screen appears.")
    print("   3) (Optional) Enable 'Hey Jarvis' from ⚙ → WAKE WORD.")


if __name__ == "__main__":
    main()
