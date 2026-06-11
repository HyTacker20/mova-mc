from __future__ import annotations

import shutil
from pathlib import Path
from types import TracebackType


class Workspace:
    def __init__(self, temp_path: str) -> None:
        self.temp_path = Path(temp_path)

    def __enter__(self) -> Path:
        self.temp_path.mkdir(parents=True, exist_ok=True)
        return self.temp_path

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.temp_path.exists():
            shutil.rmtree(str(self.temp_path))
