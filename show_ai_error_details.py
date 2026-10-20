"""Show OpenAI error codes in the Django log without printing keys or error bodies."""

import ast
from datetime import datetime
from pathlib import Path
import re
import shutil


def main():
    root = Path(__file__).resolve().parent
    target = root / "backend" / "experiments" / "ai_suggestions.py"
    if not target.is_file():
        raise SystemExit("Save this helper in the hardyboys-ml-project folder first.")
    original = target.read_text(encoding="utf-8-sig")
    if "AI suggestion provider failed: %s | code=%s" in original:
        print("Detailed error logging is already installed.")
        return

    pattern = (r'(?m)^([ \t]*)logger\.warning\("AI suggestion provider failed: %s", '
               r'type\(error\)\.__name__\)$')

    def replacement(match):
        indent = match.group(1)
        return "\n".join([
            indent + "logger.warning(",
            indent + '    "AI suggestion provider failed: %s | code=%s | type=%s | status=%s",',
            indent + '    type(error).__name__, getattr(error, "code", None),',
            indent + '    getattr(error, "type", None), getattr(error, "status_code", None),',
            indent + ")",
        ])

    updated, count = re.subn(pattern, replacement, original, count=1)
    if count != 1:
        raise SystemExit("The expected logging line was not found. No files were changed.")
    ast.parse(updated)
    backup = root / "local_jobs" / "backups" / (
        "ai-log-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".py")
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup)
    target.write_text(updated, encoding="utf-8")
    print("Updated backend/experiments/ai_suggestions.py.")
    print("Restart Django, click Suggest Experiment once, and read the AI suggestion provider failed line.")
    print("The log now includes the provider error code, error type, and HTTP status.")


if __name__ == "__main__":
    main()
