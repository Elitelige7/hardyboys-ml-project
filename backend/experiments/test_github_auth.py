"""Exercise the real OAuth redirects and callback using mocked GitHub HTTP."""

import json
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import requests
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from .models import Experiment


TEST_PROVIDER = {
    "github": {
        "APP": {"client_id": "github-test-client-id", "secret": "github-test-client-secret", "key": ""},
        "SCOPE": [],
        "OAUTH_PKCE_ENABLED": True,
    },
}


@override_settings(
    SOCIALACCOUNT_PROVIDERS=TEST_PROVIDER,
    MLFLOWPRO_GITHUB_ALLOWED_USERS=("Elitelige7", "elsow1", "KHD-wq"),
    ACCOUNT_RATE_LIMITS={},
)
class GitHubAuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        self.http_calls = []

    def csrf(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        return self.client.cookies["csrftoken"].value

    def start_login(self, **request_options):
        token = self.csrf()
        response = self.client.post("/accounts/github/login/", HTTP_X_CSRFTOKEN=token, **request_options)
        self.assertEqual(response.status_code, 302)
        return response, parse_qs(urlparse(response["Location"]).query)

    def github_response(self, method, url, **kwargs):
        self.http_calls.append((method.upper(), url, kwargs))
        if method.upper() == "POST" and url == "https://github.com/login/oauth/access_token":
            value = {"access_token": "test-provider-token", "token_type": "bearer", "expires_in": 28800,
                     "refresh_token": "test-refresh-token"}
        elif method.upper() == "GET" and url == "https://api.github.com/user":
            value = {"id": self.github_id, "login": self.github_name, "name": "Test Team Member",
                     "email": "unused-public-email@example.com"}
        else:
            raise AssertionError("Unexpected external request in OAuth test: " + url)
        result = requests.Response()
        result.status_code = 200
        result.headers["content-type"] = "application/json"
        result._content = json.dumps(value).encode("utf-8")
        return result

    def finish_login(self, name="Elitelige7", identity=314159):
        self.github_name, self.github_id = name, identity
        _, query = self.start_login()
        with patch("requests.sessions.Session.request", side_effect=self.github_response):
            response = self.client.get("/accounts/github/login/callback/", {
                "code": "temporary-test-authorization-code", "state": query["state"][0],
            })
        return response

    def test_dashboard_has_sign_in_and_does_not_expose_credentials(self):
        response = self.client.get("/")
        self.assertContains(response, "Sign in with GitHub")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertNotContains(response, "github-test-client-secret")
        self.assertNotContains(response, "github-test-client-id")
        self.assertContains(response, "Shared Experiment Notes")

    def test_missing_credentials_disable_button_and_fail_gracefully(self):
        with override_settings(SOCIALACCOUNT_PROVIDERS={"github": {"APP": {"client_id": "", "secret": ""}}}):
            response = self.client.get("/")
            self.assertContains(response, 'id="github-sign-in-btn" disabled')
            token = self.csrf()
            response = self.client.post("/accounts/github/login/", HTTP_X_CSRFTOKEN=token)
            self.assertEqual(response.status_code, 503)
            self.assertContains(response, "temporarily unavailable", status_code=503)
            self.assertEqual(self.client.get("/accounts/github/login/callback/").status_code, 503)

    def test_login_requires_post_and_csrf(self):
        self.assertEqual(self.client.get("/accounts/github/login/").status_code, 405)
        self.assertEqual(self.client.post("/accounts/github/login/").status_code, 403)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authorization_redirect_uses_state_pkce_and_exact_local_callback(self):
        response, query = self.start_login(HTTP_HOST="127.0.0.1:8000")
        self.assertEqual(urlparse(response["Location"]).netloc, "github.com")
        self.assertEqual(query["client_id"], ["github-test-client-id"])
        self.assertEqual(query["redirect_uri"], ["http://127.0.0.1:8000/accounts/github/login/callback/"])
        self.assertTrue(query["state"][0])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(len(query["code_challenge"][0]), 43)
        self.assertNotIn("scope", query)
        self.assertNotIn("github-test-client-secret", response["Location"])

    def test_https_proxy_produces_https_callback(self):
        with override_settings(ALLOWED_HOSTS=["testserver", "hardyboys-ml-project.onrender.com"]):
            _, query = self.start_login(HTTP_HOST="hardyboys-ml-project.onrender.com",
                                        HTTP_ORIGIN="https://hardyboys-ml-project.onrender.com",
                                        HTTP_X_FORWARDED_PROTO="https", secure=True)
        self.assertEqual(query["redirect_uri"], [
            "https://hardyboys-ml-project.onrender.com/accounts/github/login/callback/",
        ])

    def test_allowed_github_callback_creates_session_without_saving_tokens(self):
        response = self.finish_login("elitelige7")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        user = get_user_model().objects.get(pk=self.client.session["_auth_user_id"])
        self.assertEqual(user.username, "elitelige7")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.email, "")
        account = SocialAccount.objects.get(user=user)
        self.assertEqual(account.provider, "github")
        self.assertEqual(account.uid, "314159")
        self.assertEqual(SocialToken.objects.count(), 0)
        token_call = self.http_calls[0][2]["data"]
        self.assertEqual(token_call["client_secret"], "github-test-client-secret")
        self.assertTrue(token_call["code_verifier"])
        self.assertEqual(len(self.http_calls), 2)
        page = self.client.get("/")
        self.assertContains(page, "Signed in as")
        self.assertContains(page, "elitelige7")
        self.assertNotContains(page, "test-provider-token")

    def test_returning_github_account_reuses_user(self):
        self.assertEqual(self.finish_login().status_code, 302)
        original_id = self.client.session["_auth_user_id"]
        self.client.logout()
        self.assertEqual(self.finish_login().status_code, 302)
        self.assertEqual(self.client.session["_auth_user_id"], original_id)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(SocialAccount.objects.count(), 1)

    def test_unlisted_github_account_is_denied_before_user_creation(self):
        response = self.finish_login("not-on-the-team", identity=271828)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "access list.", status_code=403)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(get_user_model().objects.count(), 0)
        self.assertEqual(SocialAccount.objects.count(), 0)

    def test_returning_user_removed_from_allowlist_cannot_sign_in_again(self):
        self.assertEqual(self.finish_login().status_code, 302)
        self.client.logout()
        with override_settings(MLFLOWPRO_GITHUB_ALLOWED_USERS=("elsow1",)):
            response = self.finish_login()
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_invalid_state_cannot_exchange_code_or_create_session(self):
        self.start_login()
        with patch("requests.sessions.Session.request") as external:
            response = self.client.get("/accounts/github/login/callback/", {
                "code": "untrusted-code", "state": "does-not-match-session",
            })
        external.assert_not_called()
        self.assertLess(response.status_code, 500)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logged_in_predictions_work_with_csrf_and_reject_missing_token(self):
        self.assertEqual(self.finish_login().status_code, 302)
        token = self.csrf()
        payload = {"review": "This was an excellent movie with great acting."}
        denied = self.client.post("/api/predict/", payload, content_type="application/json")
        self.assertEqual(denied.status_code, 403)
        response = self.client.post("/api/predict/", payload, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["prediction"], "Positive")
        self.assertContains(self.client.get("/"), "X-CSRFToken")

    def test_authenticated_team_can_create_experiment_but_anonymous_cannot(self):
        payload = {"name": "OAuth-created experiment", "description": "OAuth test fixture", "dataset": "Test"}
        anonymous = self.client.post("/api/experiments/", payload, content_type="application/json")
        self.assertIn(anonymous.status_code, [401, 403])
        self.assertEqual(self.finish_login().status_code, 302)
        response = self.client.post("/api/experiments/", payload, content_type="application/json",
                                    HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Experiment.objects.filter(name="OAuth-created experiment").exists())

    def test_logout_requires_csrf_and_ends_session(self):
        self.assertEqual(self.finish_login().status_code, 302)
        self.assertEqual(self.client.get("/team/logout/").status_code, 405)
        self.assertEqual(self.client.post("/team/logout/").status_code, 403)
        response = self.client.post("/team/logout/", HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_native_password_signup_is_unavailable(self):
        self.assertEqual(self.client.get("/accounts/signup/").status_code, 404)
        self.assertEqual(self.client.get("/accounts/password/reset/").status_code, 404)
