"""Entry point for ``mova web``.

Starts a uvicorn server on localhost and optionally opens the browser.
"""

from __future__ import annotations

import sys


def main(host: str = "127.0.0.1", port: int = 8000, *, dev: bool = False, no_browser: bool = False) -> None:
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

    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="warning")
