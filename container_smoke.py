"""Check that the running web container serves its models and predicts reviews."""

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
