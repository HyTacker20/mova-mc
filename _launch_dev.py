"""Launch the MovaMC dev server."""
import subprocess
import sys
from pathlib import Path

backend = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
cmd = [str(backend), "-m", "backend", "--dev", "--no-browser"]
subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parent), stdout=sys.stdout, stderr=sys.stderr)
