API reference
=============

All paths below are relative to the Django application's origin. The dashboard
uses same-origin requests locally and on Render.

Prediction
----------

``POST /api/predict/`` accepts a JSON object:

.. code-block:: json

   {"review": "The movie was excellent.", "version_id": null}

``review`` must be a nonblank string of at most 10,000 characters. Omit
``version_id`` or send null to use the original Logistic Regression model.
Send a registered model-version UUID to select that pipeline.

A successful response contains:

.. list-table::
   :header-rows: 1

   * - Field
     - Meaning
   * - ``prediction``
     - ``Positive`` or ``Negative``.
   * - ``confidence``
     - Largest predicted class probability, between zero and one.
   * - ``model_name``
     - Classifier identifier used for inference.
   * - ``version_id``
     - Selected UUID, or null for the original default model.

HTTP 400 indicates invalid input, 404 indicates an unknown version, and 503
indicates an unavailable or incompatible model file. The endpoint is public.
When using a logged-in Django session, include ``X-CSRFToken`` on the POST.

PowerShell example using an anonymous request:

.. code-block:: powershell

   $body = @{ review = "This was an excellent movie with great acting." } | ConvertTo-Json
   Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/predict/" -Method Post -ContentType "application/json" -Body $body

Experiment and version endpoints
--------------------------------

.. list-table::
   :header-rows: 1
   :widths: 38 22 40

   * - Endpoint
     - Methods
     - Access
   * - ``/api/model-versions/``
     - GET
     - Public read-only version registry.
   * - ``/api/model-versions/<uuid>/``
     - GET
     - Public read-only version details.
   * - ``/api/experiment-results/``
     - GET; authenticated writes
     - Public metrics; writes require authentication.
   * - ``/api/experiments/``
     - GET, POST
     - Authentication required.
   * - ``/api/model-settings/``
     - GET, POST
     - Authentication required.

The experiment, settings, and result viewsets also expose detail URLs with
GET, PUT, PATCH, and DELETE subject to their permission policy. The registry
exposes metadata and provenance but excludes the internal artifact filename.

Deleting an experiment with registered model versions is restricted by its
database relationship. Model lifecycle changes should preserve the record of
which fitted artifact produced a result.

AI suggestions
--------------

``POST /api/ai-suggestions/`` expects ``goal`` and an optional ``version_id``.
The request needs an ``X-MLFlowPro-Access-Code`` header containing the private
team code. The server also needs its OpenAI key and team-code environment
settings. Do not put an OpenAI key in browser JavaScript or the team-code box.

The response contains a draft suggestion, the provider model identifier, and a
review notice. The request context excludes held-out test scores, review text,
and artifact paths. Suggestions do not execute automatically.

HTTP 403 means the team code did not match, 429 means the application's local
request throttle was reached, 503 means required configuration is absent, and
502 means provider generation failed or produced unusable output. An OpenAI
quota error was observed during setup; a successful funded provider request is
still required before presenting live generation as verified.

WebSocket notes
---------------

Connect to ``/ws/experiment-notes/`` using ``ws://`` locally or ``wss://`` over
HTTPS. The first JSON message must authenticate with ``type`` set to
``authenticate`` and an ``access_code``. A valid connection receives a ``ready``
message with the current document.

A save message uses ``type: save``, a string ``body`` of at most 4,000 characters,
and the document's integer ``revision``. An optional ``request_id`` lets the
browser identify its save acknowledgement. Successful saves are broadcast as
document updates; stale revisions receive ``conflict`` and the latest document.
The client can request the current document using ``type: load``.

GitHub login routes
-------------------

* ``POST /accounts/github/login/`` starts the CSRF-protected OAuth flow.
* ``GET /accounts/github/login/callback/`` validates the returned state and code.
* ``POST /team/logout/`` ends the session and requires a CSRF token.

The GitHub app client secret is exchanged server-side and is never embedded in
the dashboard. The access list applies to new and returning social sign-ins.
