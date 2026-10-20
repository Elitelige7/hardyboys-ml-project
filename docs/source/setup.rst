Installation and local setup
============================

Prerequisites
-------------

Use Python 3.11, Git, and a terminal. These instructions use Windows PowerShell.
Run project commands from the repository root, which contains the ``backend``
directory. The project's Python dependencies are pinned in
``backend/requirements.txt``; documentation dependencies are separate.

Create your environment
-----------------------

For a new checkout:

.. code-block:: powershell

   git clone https://github.com/Elitelige7/hardyboys-ml-project.git
   cd hardyboys-ml-project
   git switch feature/django-review-prediction
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r backend/requirements.txt

For an existing checkout, activate its existing environment instead of creating
another one. The ``(.venv)`` prefix confirms activation. Use ``python -m pip``
so packages install into the same interpreter that runs the app.

Configuration
-------------

Create ``backend/.env`` in your editor. A minimal local file contains:

.. code-block:: text

   DJANGO_SECRET_KEY=replace_with_a_generated_secret
   DJANGO_DEBUG=True

Generate the secret value in your activated environment:

.. code-block:: powershell

   python -c "import secrets; print(secrets.token_urlsafe(50))"

The local database defaults to SQLite when ``DATABASE_URL`` is absent. A
PostgreSQL URL selects the hosted database configuration. Store credentials in
the local environment file or Render environment settings, and exclude them
from Git.

Prepare the database and model registry
---------------------------------------

.. code-block:: powershell

   python backend/manage.py migrate
   python backend/manage.py loaddata backend/demo_results.json
   python register_model_versions.py
   python publish_model.py restore
   python backend/manage.py runserver

Open http://127.0.0.1:8000/ and leave the server terminal running. The restore
command imports any committed published-model bundles; it reports that none
were found if there are no bundles in that checkout. The app uses included
saved models, so a dataset download is unnecessary for normal predictions.

Try a positive review and a negative review, select a saved version, and click
**Load Experiment Metrics**. The same result response fills the table and the
D3 comparison chart.

Dataset for training
--------------------

Download the CSV from the `IMDb 50K dataset page
<https://www.kaggle.com/datasets/lakshmi25npathi/imdb-dataset-of-50k-movie-reviews>`_.
Extract it to ``data/IMDB Dataset.csv``. The training scripts expect ``review``
and ``sentiment`` columns, with ``positive`` and ``negative`` labels. Do not add
the dataset to Git.

Optional features
-----------------

* GitHub sign-in needs ``GITHUB_CLIENT_ID``, ``GITHUB_CLIENT_SECRET``, and
  ``GITHUB_ALLOWED_USERS``. See :doc:`deployment`.
* AI suggestions need ``OPENAI_API_KEY`` and the private
  ``MLFLOWPRO_AI_ACCESS_CODE``. A provider quota error means real generation has
  not succeeded; the rest of the dashboard can still operate.
* Shared notes use ``MLFLOWPRO_AI_ACCESS_CODE`` too. They do not make an LLM
  request and do not require OpenAI credit.

Build this handbook
-------------------

.. code-block:: powershell

   python -m pip install -r requirements-docs.txt
   python -m sphinx -n -W --keep-going -b html docs/source docs/build/html
   Start-Process .\docs\build\html\index.html

The HTML build is local documentation; it is separate from the Django
dashboard. The documentation workflow on GitHub runs the same build check.
