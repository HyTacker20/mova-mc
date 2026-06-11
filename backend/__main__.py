"""Entry point for ``mova web``.

Starts a uvicorn server on localhost and optionally opens the browser.
"""

from __future__ import annotations

import socket
import sys


def _is_port_available(host: str, port: int) -> bool:
    """Check if a port is free by attempting to bind to it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def main(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    dev: bool = False,
    no_browser: bool = False,
) -> None:
    try:
        import uvicorn
    except ImportError:
        print(
            "Web UI requires additional packages.\n"
            "Install with:  pip install mova-mc[web]\n"
            "             or: uv add fastapi uvicorn",
            file=sys.stderr,
        )
        sys.exit(1)

    import webbrowser

    from backend.app import create_app

    # Pre-flight port check so we can give a clear error before uvicorn
    # swallows the OSError internally.
    if not _is_port_available(host, port):
        print(
            f"\nERROR: Port {port} is already in use.\n"
            f"Either stop the other process or use --port <N> to pick a different port.",
            file=sys.stderr,
        )
        sys.exit(1)

    url = f"http://{host}:{port}"
    app = create_app(dev=dev)

    if not no_browser:
        import threading
        import time

        def _open() -> None:
            time.sleep(1.2)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    print(f"MovaMC web UI → {url}")
    print("Press Ctrl+C to stop.\n")

    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except OSError as exc:
        if "10048" in str(exc) or "address already in use" in str(exc).lower():
            print(
                f"\nERROR: Port {port} is already in use.\n"
                f"Either stop the other process or use --port <N> to pick a different port.",
                file=sys.stderr,
            )
            sys.exit(1)
        raise
