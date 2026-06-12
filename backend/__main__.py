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
    """Kill any process listening on *port* (Windows).

    Uses ``netstat -ano`` output and only matches the exact port
    (e.g. port 5173 must appear as ``:5173`` at the end of the
    local-address token — never ``:51730``, ``:15173``, etc.).
    """
    import platform

    if platform.system() != "Windows":
        return

    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, check=False, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return

    suffix = f":{port}"
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr = parts[1]  # e.g. "0.0.0.0:5173" or "[::1]:5173"
        if not local_addr.endswith(suffix):
            continue
        pid = parts[4]
        subprocess.run(
            ["taskkill", "/F", "/PID", pid],
            capture_output=True, check=False, timeout=5,
        )


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


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def main(
    host: str | None = None,
    port: int | None = None,
    *,
    dev: bool | None = None,
    debug: bool | None = None,
    no_browser: bool | None = None,
) -> None:
    # ── Resolve from env when caller didn't provide explicit value ──
    host = host if host is not None else os.environ.get("MOVAMC_HOST", "127.0.0.1")
    port = port if port is not None else int(os.environ.get("MOVAMC_PORT", "8000"))
    dev = dev if dev is not None else _env_bool("MOVAMC_DEV", False)
    debug = debug if debug is not None else _env_bool("MOVAMC_DEBUG", False)
    no_browser = no_browser if no_browser is not None else _env_bool("MOVAMC_NO_BROWSER", False)
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


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(prog="mova-web", description="MovaMC web UI server")
    ap.add_argument("--host", default=None, help="Bind host (env: MOVAMC_HOST)")
    ap.add_argument("--port", type=int, default=None, help="Listen port (env: MOVAMC_PORT)")
    ap.add_argument("--dev", action="store_const", const=True, default=None,
                    help="Dev mode + CORS (env: MOVAMC_DEV)")
    ap.add_argument("--debug", action="store_const", const=True, default=None,
                    help="Debug logging (env: MOVAMC_DEBUG)")
    ap.add_argument("--no-browser", action="store_const", const=True, default=None,
                    help="Skip browser (env: MOVAMC_NO_BROWSER)")
    ns = ap.parse_args()

    main(
        host=ns.host,
        port=ns.port,
        dev=ns.dev,
        debug=ns.debug,
        no_browser=ns.no_browser,
    )
