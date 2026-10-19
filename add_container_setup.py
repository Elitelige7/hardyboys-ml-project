"""Add Docker packaging and a GitHub Actions container check to MLFlowPro."""

from datetime import datetime
from pathlib import Path
import re


FILES = {
    "Dockerfile": '''FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install -r /tmp/requirements.txt

RUN useradd --create-home --uid 10001 appuser
RUN chown appuser:appuser /app
COPY --chown=appuser:appuser . /app
USER appuser

EXPOSE 8000
CMD ["python", "docker_start.py"]
''',
    ".dockerignore": '''.git
.github
**/.venv
**/venv
**/__pycache__
**/*.py[cod]
**/.env*
**/.pytest_cache
**/.coverage*
**/node_modules
**/.vscode
**/.DS_Store
**/Thumbs.db
**/*.sqlite3*
**/staticfiles
data
local_jobs
models/versions
docs/_build
demo.gif
*.zip

# Keep models/*.joblib and published_models/: startup restores these models.
''',
    "docker_start.py": '''"""Initialize the container's database and model files, then start Gunicorn."""

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

    arguments = [
        sys.executable, "-m", "gunicorn", "--chdir", str(ROOT / "backend"),
        "MLFlowPro.wsgi:application", "--bind", "0.0.0.0:" + os.getenv("PORT", "8000"),
        "--workers", os.getenv("WEB_CONCURRENCY", "1"), "--timeout", "120",
        "--access-logfile", "-", "--error-logfile", "-",
    ]
    os.execv(sys.executable, arguments)


if __name__ == "__main__":
    main()
''',
    "container_smoke.py": '''"""Check that the running web container serves its models and predicts reviews."""

import argparse
import json
import math
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def request_json(base_url, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(base_url + path, data=body, headers={
        "Accept": "application/json", "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=10) as response:
            require(response.status == 200, f"Unexpected HTTP status: {response.status}")
            return json.load(response)
    except HTTPError as error:
        detail = error.read(2000).decode("utf-8", errors="replace")
        raise RuntimeError(f"{path}: HTTP {error.code}: {detail}") from error


def wait_for_homepage(base_url, seconds):
    deadline = time.monotonic() + seconds
    last_error = "No response"
    while time.monotonic() < deadline:
        try:
            with urlopen(base_url + "/", timeout=3) as response:
                require(response.status == 200, "Homepage did not return HTTP 200.")
                require(b"<html" in response.read().lower(), "Homepage is not HTML.")
                return
        except (OSError, URLError, RuntimeError) as error:
            last_error = str(error)
            time.sleep(1)
    raise RuntimeError(f"Container did not become ready: {last_error}")


def finite_score(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and 0 <= value <= 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--wait-seconds", type=int, default=60)
    arguments = parser.parse_args()
    base_url = arguments.url.rstrip("/")
    wait_for_homepage(base_url, arguments.wait_seconds)
    print("PASS: homepage is available", flush=True)

    versions = request_json(base_url, "/api/model-versions/")
    require(isinstance(versions, list) and len(versions) >= 2,
            "Expected at least the two imported model versions.")
    require({"naive_bayes", "logistic_regression"}.issubset(
        {version["model_name"] for version in versions}), "A baseline model is missing.")
    print(f"PASS: registry lists {len(versions)} model versions", flush=True)

    registry = {version["id"]: version for version in versions}
    for manifest in (Path(__file__).resolve().parent / "published_models").glob("*/manifest.json"):
        package = json.loads(manifest.read_text(encoding="utf-8"))
        require(package["version_id"] in registry, "A published model is missing from the container.")
        require(registry[package["version_id"]]["metrics"] == package["metrics"],
                "A published model's recorded metrics changed during restoration.")
        print(f"PASS: published version {package['version_id']} retains its metrics", flush=True)

    results = request_json(base_url, "/api/experiment-results/")
    require(isinstance(results, list) and bool(results), "No experiment results were loaded.")
    for result in results:
        require(finite_score(result.get("accuracy")), "Invalid accuracy in experiment results.")
        require(finite_score(result.get("f1_score")), "Invalid F1 score in experiment results.")
    print(f"PASS: {len(results)} experiment results contain valid scores", flush=True)

    review = "This was an excellent movie with great acting."
    default = request_json(base_url, "/api/predict/", {"review": review})
    require(default.get("prediction") in {"Positive", "Negative"}, "Invalid default prediction.")
    require(finite_score(default.get("confidence")), "Invalid default confidence.")
    require(default.get("version_id") is None, "Default prediction unexpectedly selected a version.")
    print("PASS: default model predicts a review", flush=True)

    for version in versions:
        prediction = request_json(base_url, "/api/predict/", {
            "review": review, "version_id": version["id"],
        })
        require(prediction.get("version_id") == version["id"], "Prediction used the wrong version.")
        require(prediction.get("model_name") == version["model_name"], "Prediction used the wrong model.")
        require(prediction.get("prediction") in {"Positive", "Negative"}, "Invalid prediction label.")
        require(finite_score(prediction.get("confidence")), "Invalid prediction confidence.")
        print(f"PASS: {version['model_name']} version {version['id']} predicts a review", flush=True)

    print("Container smoke checks passed.", flush=True)


if __name__ == "__main__":
    main()
''',
}

CONTAINER_JOB = '''
  # MLFlowPro: container build and smoke check
  container-smoke:
    needs: test
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: Check out repository
        uses: actions/checkout@v6
        with:
          persist-credentials: false
      - name: Set up Python for the HTTP check
        uses: actions/setup-python@v6
        with:
          python-version: "3.11"
      - name: Build application image
        run: docker build --tag mlflowpro-ci .
      - name: Start application container with an isolated demo database
        run: >-
          docker run --detach --name mlflowpro-ci
          --publish 127.0.0.1:8000:8000
          --env DJANGO_SECRET_KEY=ci-only-container-test-key-never-use-in-production
          --env DJANGO_DEBUG=True
          mlflowpro-ci
      - name: Check homepage, results, and model predictions
        run: python container_smoke.py
      - name: Show container logs
        if: always()
        run: docker logs mlflowpro-ci
      - name: Remove test container
        if: always()
        run: docker rm --force mlflowpro-ci
'''


def main():
    root = Path(__file__).resolve().parent
    prerequisites = [
        "backend/manage.py", "backend/requirements.txt", "backend/demo_results.json",
        "register_model_versions.py", "publish_model.py",
        "models/naive_bayes.joblib", "models/logistic_regression.joblib",
        ".github/workflows/backend-checks.yml",
    ]
    missing = [name for name in prerequisites if not (root / name).is_file()]
    if missing:
        raise SystemExit("Place this helper in the project root and finish the previous steps. Missing: "
                         + ", ".join(missing))

    workflow_name = ".github/workflows/backend-checks.yml"
    original = (root / workflow_name).read_text(encoding="utf-8-sig")
    if not re.search(r"^  test:\s*$", original, re.MULTILINE):
        raise SystemExit("Expected the test job from add_project_checks.py in backend-checks.yml.")
    if re.search(r"^  container-smoke:\s*$", original, re.MULTILINE):
        if not original.rstrip().endswith(CONTAINER_JOB.strip()):
            raise SystemExit("An existing container-smoke job differs from this helper. No files changed.")
        workflow = original
    else:
        workflow = original.rstrip() + "\n" + CONTAINER_JOB

    contents = {**FILES, workflow_name: workflow}
    backup = root / "local_jobs" / "backups" / (
        "container-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    for relative, content in contents.items():
        target = root / relative
        if target.is_file() and target.read_text(encoding="utf-8") != content:
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(target.read_bytes())
    for relative, content in contents.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print("Ready:", relative)
    if backup.exists():
        print("Previous files backed up at:", backup)
    print("Push these files to run the test and container-smoke jobs in GitHub Actions.")


if __name__ == "__main__":
    main()
