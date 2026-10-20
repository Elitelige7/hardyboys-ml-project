Architecture and concepts
=========================

What the application does
-------------------------

An engineer types a review and selects a saved model version. The browser sends
the text and optional version ID to Django. The server loads the corresponding
scikit-learn pipeline, calculates a prediction, and returns JSON. The browser
displays the label and model probability without reloading the page.

Training is a separate operation. A training script prepares the data, fits a
pipeline, evaluates it, and stores the settings, results, provenance, and model
snapshot. The prediction endpoint uses a fitted pipeline; it does not retrain a
model for every review.

Component responsibilities
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Component
     - Responsibility
   * - ``backend/index.html``
     - Dashboard forms, prediction requests, jQuery version selection, and D3 charts.
   * - Django and Django REST Framework
     - HTTP routes, validation, database access, and JSON responses.
   * - scikit-learn pipelines
     - TF-IDF feature extraction and sentiment classification.
   * - PostgreSQL or local SQLite
     - Experiment, configuration, result, version, and shared-note records.
   * - Optuna TPE search
     - Select classifier hyperparameters using training-only cross-validation.
   * - Local Celery worker
     - Run tuning outside the web request in another terminal.
   * - Channels and Daphne
     - ASGI HTTP serving and WebSocket note updates.
   * - django-allauth and GitHub
     - OAuth2 identity verification and team-restricted Django sessions.
   * - OpenAI integration
     - Suggest experiment settings and draft Python snippets when configured and funded.

Database records and model files
--------------------------------

The word "model" has two meanings here. A **Django model** describes a database
record. A **machine learning model** is the fitted classifier inside a saved
pipeline.

.. list-table::
   :header-rows: 1

   * - Django model
     - Stored information
   * - ``Experiment``
     - Run name, dataset, description, and creation time.
   * - ``ModelSettings``
     - Algorithm, TF-IDF feature settings, and hyperparameter JSON for a run.
   * - ``ExperimentResult``
     - Measured test accuracy, macro F1, and final training duration.
   * - ``ModelVersion``
     - UUID, parameters, metrics, provenance, and the snapshot filename.
   * - ``CollaborationNote``
     - Shared planning text, revision number, and last-update time.

``ModelSettings`` fulfills the assignment's hyperparameter-settings concept.
Versioned pipelines live in ``models/versions/``. Their metadata lives in the
database; the pipeline bytes do not. Selected bundles in ``published_models/``
allow deployment to restore both the model file and its associated metadata.

Real-time collaboration
-----------------------

Two browser tabs connect to ``/ws/experiment-notes/`` and authenticate using the
team code in the first message. A successful save updates the database and
broadcasts the new note to connected clients. Each save includes the revision
the editor started from. If another editor saved first, the server rejects the
stale write and returns the current document instead of replacing it.

This is collaboration on saved experiment-planning notes. It is not simultaneous
editing of training parameters or character-by-character text merging. The
in-memory channel layer supports the demo's single server process; multiple
processes or instances require a shared channel layer such as Redis.

Authentication and suggestions
------------------------------

GitHub OAuth verifies identity, then the social-account adapter checks the
GitHub username against the configured team list. Approved users receive a
Django session. Authenticated experiment APIs require that session or another
supported authentication method. Browser prediction requests include the CSRF
token so they keep working after sign-in.

The public prediction demo remains available without an account. Shared notes
and AI suggestions additionally use their existing private team-code gate.
The LLM returns a draft suggestion; the server does not execute generated code
or automatically accept proposed hyperparameters.
