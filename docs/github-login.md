# GitHub OAuth2 team sign-in

The dashboard can sign team members in through GitHub. GitHub verifies their
identity; Django creates a session only when their GitHub username is allowed.
The default list is `Elitelige7,elsow1,KHD-wq`. Add your professor's exact GitHub
username to `GITHUB_ALLOWED_USERS` if they need team access.

Public predictions, the version list, and performance results remain accessible
without signing in. Existing authenticated experiment APIs also accept the
GitHub session. AI suggestions and shared notes continue using their team access
code. GitHub sign-in does not require OpenAI credits.

## 1. Install the feature from PowerShell

Save `add_github_login.py` beside `publish_model.py` in your project root. Stop
your local Django server with Ctrl+C, then run:

```powershell
cd C:\Users\elige\hardyboys-ml-project
.\.venv\Scripts\Activate.ps1
python add_github_login.py
python -m pip install -r backend/requirements.txt
python backend/manage.py migrate
python -m pytest -q
```

The helper preserves your dashboard's existing styles and cards. It adds a
sign-in strip and a CSRF token on prediction requests. Backups of edited files
are stored under `local_jobs/backups/`, which your project already ignores.

## 2. Register one GitHub OAuth application

Open https://github.com/settings/applications/new and enter:

| Field | Value |
| --- | --- |
| Application name | HardyBoys MLFlowPro |
| Homepage URL | `https://hardyboys-ml-project.onrender.com/` |
| Authorization callback URL | `https://hardyboys-ml-project.onrender.com/accounts/github/login/callback/` |
| Additional callback URL | `http://127.0.0.1:8000/accounts/github/login/callback/` |

Use **Add callback URL** for the second address. Keep device flow disabled; this
feature uses the browser flow. Expiring access tokens can remain enabled: the
server uses a token immediately to verify identity and does not save it for
later API use. Click **Register application**, then **Generate a new client
secret**. GitHub supplies the Client ID and Client Secret.

## 3. Set your local credentials

Open `backend/.env` in VS Code. Add these lines, replacing the first two values:

```dotenv
GITHUB_CLIENT_ID=your_actual_github_client_id
GITHUB_CLIENT_SECRET=your_actual_github_client_secret
GITHUB_ALLOWED_USERS=Elitelige7,elsow1,KHD-wq
```

Leave your existing Django, database, and OpenAI settings in the file. Keep
`backend/.env` out of Git. Restart the local server:

```powershell
python backend/manage.py runserver
```

Visit http://127.0.0.1:8000/ (use this hostname rather than `localhost` so the
callback matches). Click **Sign in with GitHub** and authorize the application.
You should return to the dashboard with **Signed in as** and your username.
Run a prediction, then sign out. The authorization request asks for no additional
GitHub scopes; it does not request repository access or private email access.

## 4. Deploy to Render

Review and commit the feature files on your existing feature branch:

```powershell
git add add_github_login.py backend/MLFlowPro/settings.py backend/MLFlowPro/urls.py
git add backend/experiments/github_auth.py backend/experiments/test_github_auth.py
git add backend/templates/experiments/github_auth_error.html backend/index.html
git add backend/requirements.txt docs/github-login.md
git diff --cached --stat
git commit -m "Add GitHub OAuth2 team sign-in"
git push
```

In https://dashboard.render.com/, open `hardyboys-ml-project` and **Environment**.
Add the same three variables from step 3, using your real values. Keep the
existing environment variables and the start command `python run_asgi.py`.
Deploy the branch containing your commit. Your existing build script must run
`python backend/manage.py migrate --noinput`; allauth supplies the new database
migrations, so no new experiments migration is needed for this feature.

Test sign-in, prediction, and sign-out at the public HTTPS address. Check the
GitHub Actions run after pushing. A successful mocked test run cannot verify
your real GitHub credentials or Render environment settings.

## How it works

1. A CSRF-protected form starts the authorization request. Allauth stores random
   state and a PKCE verifier in the Django session.
2. GitHub redirects to the matching callback URL with a temporary code.
3. Django validates the state, exchanges the code server-side, and fetches the
   GitHub account ID and username.
4. The adapter checks the username against `GITHUB_ALLOWED_USERS`, including on
   returning sign-ins. Unlisted accounts receive HTTP 403 without a new account.
5. Approved accounts receive a Django session. Their account has no local
   password; the client secret and provider tokens are never sent to the page.

GitHub account IDs identify saved social accounts. The access list uses
case-insensitive GitHub usernames; update it if a teammate renames their account.
Removing someone prevents their next sign-in; it does not revoke an already
active Django session. Do not describe this class demo as complete enterprise
identity management.

## Verification and troubleshooting

`test_github_auth.py` tests the actual authorization redirect and callback with
mocked GitHub HTTP responses, state/PKCE, team restrictions, returning users,
CSRF, authenticated API access, prediction after login, and logout. It also
checks that credentials and tokens are absent from the page and no social token
is stored in the database.

- **Disabled sign-in:** set both GitHub credential variables and restart/deploy.
- **Redirect URI mismatch:** copy the callback exactly, including the scheme,
  hostname, and trailing slash; register both local and live callbacks.
- **403 after GitHub authorization:** confirm the GitHub username is allowed.
- **CSRF failure after sign-in:** refresh the dashboard before submitting; old
  tabs can have the token issued before the login session changed.
- **Missing table error:** run migrations against the database used by the app.
- **MultipleObjectsReturned for SocialApp:** credentials belong in the settings
  environment configuration; do not create a second GitHub SocialApp in admin.

References:

- https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app
- https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps
- https://docs.allauth.org/en/latest/installation/quickstart.html
- https://docs.allauth.org/en/latest/socialaccount/provider_configuration.html
