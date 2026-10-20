"""Start one Daphne process for HTTP and WebSocket requests on the same port."""

import os
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parent
    port = os.environ.get("PORT", "8000")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise SystemExit("PORT must be a number between 1 and 65535.")
    os.chdir(root / "backend")
    os.execv(sys.executable, [sys.executable, "-m", "daphne", "-b", "0.0.0.0",
                             "-p", port, "MLFlowPro.asgi:application"])


if __name__ == "__main__":
    main()
