"""Initialize the container's database and model files, then start Daphne."""

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def main():
    if not os.environ.get("DJANGO_SECRET_KEY"):
        raise SystemExit("Set DJANGO_SECRET_KEY when starting the container.")
    commands = [
        ["backend/manage.py", "collectstatic", "--noinput"],
        ["backend/manage.py", "migrate", "--noinput"],
        ["backend/manage.py", "loaddata", "backend/demo_results.json"],
        ["register_model_versions.py"],
        ["publish_model.py", "restore"],
    ]
    for arguments in commands:
        print("Running:", " ".join(arguments), flush=True)
        subprocess.run([sys.executable, *arguments], cwd=ROOT, check=True)

    os.execv(sys.executable, [sys.executable, str(ROOT / "run_asgi.py")])


if __name__ == "__main__":
    main()
