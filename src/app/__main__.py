import sys
import traceback
from pathlib import Path

from loguru import logger

current_dir = Path(__file__).parent
project_root = current_dir.parent.parent  # .../src
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _main() -> None:
    from app.interfaces.cli.main import main

    main()


if __name__ == "__main__":
    try:
        _main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.exception("Error in MovaMC: {}", e)
        traceback.print_exc()
        sys.exit(1)
