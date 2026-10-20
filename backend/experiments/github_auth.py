"""GitHub OAuth entry points and the class project's team access policy."""

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.github.views import oauth2_callback, oauth2_login


def github_is_configured():
    github = settings.SOCIALACCOUNT_PROVIDERS.get("github", {})
    application = github.get("APP", {})
    return bool(application.get("client_id") and application.get("secret"))


def github_login_context(request):
    return {"github_login_configured": github_is_configured()}


def authentication_message(request, message, status):
    return render(request, "experiments/github_auth_error.html", {
        "authentication_message": message,
    }, status=status)


class TeamSocialAccountAdapter(DefaultSocialAccountAdapter):
    def allowed(self, sociallogin):
        github_name = str(sociallogin.account.extra_data.get("login", "")).casefold()
        allowed = {name.casefold() for name in settings.MLFLOWPRO_GITHUB_ALLOWED_USERS}
        return sociallogin.account.provider == "github" and github_name in allowed

    def pre_social_login(self, request, sociallogin):
        # Runs for returning accounts too, before a Django login session is issued.
        if not self.allowed(sociallogin):
            raise ImmediateHttpResponse(authentication_message(
                request, "This GitHub account is not on the project team's access list.", 403,
            ))
        return super().pre_social_login(request, sociallogin)

    def is_open_for_signup(self, request, sociallogin):
        return self.allowed(sociallogin)

    def populate_user(self, request, sociallogin, data):
        # Identity uses GitHub's account ID and login; no private email permission is needed.
        fields = dict(data)
        fields["email"] = ""
        sociallogin.email_addresses = []
        return super().populate_user(request, sociallogin, fields)


@require_POST
@csrf_protect
def github_login(request):
    if not github_is_configured():
        return authentication_message(request, "Team sign-in is temporarily unavailable.", 503)
    return oauth2_login(request)


@require_GET
def github_callback(request):
    if not github_is_configured():
        return authentication_message(request, "Team sign-in is temporarily unavailable.", 503)
    return oauth2_callback(request)


@require_POST
@csrf_protect
def team_logout(request):
    logout(request)
    return redirect("/")
