#!/usr/bin/env bash
set -e

python -m pip install -r backend/requirements.txt
python backend/manage.py collectstatic --noinput
python backend/manage.py migrate --noinput
python backend/manage.py loaddata backend/demo_results.json