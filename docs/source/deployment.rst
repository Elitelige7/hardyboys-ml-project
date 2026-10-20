Deployment, testing, and project scope
======================================

Render configuration
--------------------

The public web demo runs at https://hardyboys-ml-project.onrender.com/.
Its service should deploy the branch that contains the team's current code.
During development that branch is ``feature/django-review-prediction``.
Commands below assume the service root is the repository root.

The build script must install backend dependencies, collect static files, apply
migrations, load recorded demo results, register the original model versions,
and restore selected published bundles. Keep those existing initialization
steps when changing the start command.

The ASGI start command is:

.. code-block:: text

   python run_asgi.py

This starts Daphne bound to Render's supplied port and serves Django HTTP
requests plus the notes WebSocket. Gunicorn WSGI alone cannot serve the
implemented WebSocket route.

Environment variables
---------------------

.. list-table::
   :header-rows: 1

   * - Variable
     - Purpose
   * - ``DJANGO_SECRET_KEY``
     - Django signing secret, generated for the deployment.
   * - ``DJANGO_DEBUG``
     - ``False`` for the deployed service.
   * - ``DATABASE_URL``
     - Hosted PostgreSQL connection URL.
   * - ``GITHUB_CLIENT_ID`` and ``GITHUB_CLIENT_SECRET``
     - GitHub OAuth application's credentials.
   * - ``GITHUB_ALLOWED_USERS``
     - Comma-separated approved GitHub usernames.
   * - ``MLFLOWPRO_AI_ACCESS_CODE``
     - Private team code for notes and AI suggestion requests.
   * - ``OPENAI_API_KEY``
     - Server-side provider key for the optional suggestion feature.
   * - ``OPENAI_MODEL``
     - Configured suggestion model; the integration default is ``gpt-5.4-mini``.

Render supplies ``RENDER_EXTERNAL_HOSTNAME`` and ``PORT`` to its service. The
project uses the hostname in allowed-host and trusted-origin configuration.
Keep credential values out of source, screenshots, and the generated handbook.

GitHub OAuth setup
------------------

Create an OAuth application under GitHub's developer settings. Register both
of these exact callback URLs, including the trailing slash:

.. code-block:: text

   https://hardyboys-ml-project.onrender.com/accounts/github/login/callback/
   http://127.0.0.1:8000/accounts/github/login/callback/

Enter its Client ID and Client Secret in the local environment and in Render.
The default approved usernames are ``Elitelige7,elsow1,KHD-wq``. Add the
instructor's exact username if they need team login. GitHub repository
collaborator access is a separate course requirement.

The implementation requests no additional repository or private-email scope,
uses OAuth state and PKCE, and does not retain provider tokens. Signed-in users
receive Django sessions. Removing a username blocks its next social login;
it does not invalidate an existing session automatically. This is a team
authentication demo, not a complete enterprise identity-management system.

Checks and continuous integration
---------------------------------

Install test dependencies and run the project checks:

.. code-block:: powershell

   python -m pip install -r requirements-dev.txt
   python backend/manage.py check
   python backend/manage.py makemigrations --check --dry-run
   python -m pytest -q

Tests cover experiment APIs, model-version predictions, invalid inputs, model
publication, AI request validation with a mocked provider, WebSocket note
updates and conflicts, and OAuth callbacks with mocked GitHub HTTP responses.
Provider mocks do not prove real credentials or paid API access work.

The backend GitHub Actions workflow runs the configured application checks.
The documentation workflow builds these pages with warnings treated as errors.
Check the actual Actions run after each push instead of assuming a committed
workflow has passed. The container setup includes a Dockerfile, initialization
script, and HTTP smoke-check script; confirm the container workflow run before
claiming a successful Docker build.

For a presentation, test the live site in a fresh browser session: sign in,
submit positive and negative reviews, switch a model version, load metrics,
and sign out. Use two tabs to demonstrate shared-note saves. Confirm real LLM
generation separately if the provider account has usable credit.

Implemented scope and remaining limitations
-------------------------------------------

* The dashboard supports saved-model inference, a version selector, metrics,
  and D3 charts.
* The tracked trainer records actual experiments and supports TPE tuning.
* Celery tuning has run locally with a filesystem broker; no hosted training
  worker is established by the web deployment alone.
* Shared notes use persistent records and single-process WebSocket broadcasts.
  Multi-instance collaboration needs a shared channel layer.
* GitHub OAuth code and tests are implemented; real credentials and callbacks
  must be verified in each environment.
* OpenAI suggestion code is implemented, but a quota error blocked actual
  generation during setup. Provider funding and a successful request remain
  necessary to demonstrate that feature live.
* Render hosts the web demo. A deployed Kubernetes cluster is not part of the
  implementation described here.

Final submission review
-----------------------

The README should match the implemented scope and measured results, credit
each member's actual work, embed a committed ``demo.gif``, and link to the live
app. Refresh the walkthrough if it needs to show the new features. Confirm all
three members have contributed genuine code commits and the instructor has
been added as a repository collaborator.

Useful references
-----------------

* `Sphinx quickstart <https://www.sphinx-doc.org/en/master/usage/quickstart.html>`_
* `GitHub OAuth app registration <https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app>`_
* `django-allauth configuration <https://docs.allauth.org/en/latest/installation/quickstart.html>`_
* `Render deployment troubleshooting <https://render.com/docs/troubleshooting-deploys>`_
