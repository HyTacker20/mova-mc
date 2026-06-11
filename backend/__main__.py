"""Entry point for ``mova web``.

Starts a uvicorn server on localhost and optionally opens the browser.
In dev mode (``--dev``) also starts the Vite dev server with hot-reload.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
_VITE_PORT = 5173


def _is_port_available(host: str, port: int) -> bool:
    """Check if a port is free by attempting to bind to it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _build_frontend() -> None:
    """Run ``npm run build`` in the frontend directory."""
    print("Building frontend...", flush=True)
    npm = shutil.which("npm") or shutil.which("npm.cmd") or "npm"
    try:
        subprocess.run([npm, "run", "build"], cwd=str(_FRONTEND_DIR), check=True)
    except FileNotFoundError:
        print(
            "WARNING: npm not found — serving last pre-built copy.",
            file=sys.stderr,
        )
    except subprocess.CalledProcessError:
        print("WARNING: frontend build failed — serving last build.", file=sys.stderr)


def _kill_port(port: int) -> None:
    """Kill any process listening on *port* (Windows)."""
    import platform

    if platform.system() != "Windows":
        return
    cmd = f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :{port}\') do taskkill /F /PID %a 2>nul'
    subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False, timeout=5)  # noqa: S602


def _start_vite() -> subprocess.Popen:
    """Start the Vite dev server on ``_VITE_PORT``."""
    _kill_port(_VITE_PORT)
    print(f"Starting Vite dev server (port {_VITE_PORT})...", flush=True)
    npm = shutil.which("npm") or shutil.which("npm.cmd") or "npm"
    return subprocess.Popen(
        [npm, "run", "dev"],
        cwd=str(_FRONTEND_DIR),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


def main(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    dev: bool = False,
    debug: bool = False,
    no_browser: bool = False,
) -> None:
    try:
        import uvicorn
    except ImportError:
        print("Web UI requires additional packages.\nInstall with: uv add fastapi uvicorn", file=sys.stderr)
        sys.exit(1)

    import webbrowser

    from app.logging_config import is_logging_configured, setup_logging
    from backend.app import create_app

    if not is_logging_configured():
        setup_logging(console_level="DEBUG" if (dev or debug) else "INFO")

    if not _is_port_available(host, port):
        print(f"\nERROR: Port {port} is already in use.", file=sys.stderr)
        sys.exit(1)

    vite_proc: subprocess.Popen | None = None

    if dev:
        os.environ["MOVAMC_DEV"] = "1"
        vite_proc = _start_vite()
        time.sleep(2.0)
        browser_url = f"http://localhost:{_VITE_PORT}"
    else:
        _build_frontend()
        browser_url = f"http://{host}:{port}"

    if not no_browser:

        def _open() -> None:
            time.sleep(0.6)
            try:
                webbrowser.open(browser_url)
            except Exception:
                print(f"Could not open browser. Go to: {browser_url}", file=sys.stderr)

        threading.Thread(target=_open, daemon=True).start()

    if dev:
        print(f"\n  ▲ Vite:   {browser_url}")
        print(f"  ▲ API:    http://localhost:{port}/api")
        print(f"  ▲ Logs:   http://localhost:{port}/api/logs/stream")
    else:
        print(f"\n  MovaMC web UI → {browser_url}")

    print("  Press Ctrl+C to stop.\n")

    try:
        if dev:
            uvicorn.run(
                "backend.app:create_app",
                host=host, port=port,
                log_level="info", reload=True,
                reload_dirs=["src", "backend"],
                factory=True,
            )
        else:
            app = create_app(dev=False)
            uvicorn.run(app, host=host, port=port, log_level="warning")
    except OSError as exc:
        if "10048" in str(exc) or "address already in use" in str(exc).lower():
            print(f"\nERROR: Port {port} is already in use.", file=sys.stderr)
            sys.exit(1)
        raise
    finally:
        if vite_proc is not None:
            vite_proc.terminate()
            vite_proc.wait()
