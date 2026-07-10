"""
google_auth_views.py
────────────────────
One-time OAuth 2.0 authorization flow to obtain a Refresh Token for
the LeaseMonkey Gmail account.

Usage (run ONCE, then never again):
  1. Start the dev server.
  2. Login as admin and visit: http://127.0.0.1:8000/google/authorize/
  3. Sign in with the1leasemonkey@gmail.com in the Google consent screen.
  4. You are redirected back; the refresh token is printed in the console
     AND automatically written to the .env file.
"""

import os
from pathlib import Path

# Allow HTTP for local development (fixes InsecureTransportError)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, HttpResponseRedirect
from google_auth_oauthlib.flow import Flow

SCOPES = ['https://www.googleapis.com/auth/calendar']
REDIRECT_URI = 'http://127.0.0.1:8000/google/oauth2callback/'


def _build_flow():
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


@staff_member_required
def google_authorize(request):
    """Step 1 – Redirect the admin to Google's consent page."""
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',          # Force consent so we always get a refresh_token
    )
    request.session['google_oauth_state'] = state
    request.session['google_oauth_code_verifier'] = flow.code_verifier
    return HttpResponseRedirect(auth_url)


@staff_member_required
def google_oauth2callback(request):
    """Step 2 – Google redirects here after the user grants permission."""
    flow = _build_flow()

    # Exchange the authorization code for credentials
    code_verifier = request.session.get('google_oauth_code_verifier')
    flow.fetch_token(
        authorization_response=request.build_absolute_uri(),
        code_verifier=code_verifier
    )

    creds = flow.credentials
    refresh_token = creds.refresh_token

    if not refresh_token:
        return HttpResponse(
            "<h2>❌ No refresh token received.</h2>"
            "<p>Make sure you set <code>prompt='consent'</code> and "
            "the user has not previously authorized this app. "
            "Try revoking access at "
            "<a href='https://myaccount.google.com/permissions'>myaccount.google.com/permissions</a> "
            "and then visit /google/authorize/ again.</p>",
            status=400,
        )

    # ── Write token to .env file automatically ──────────────────────────────────
    env_path = Path(settings.BASE_DIR) / '.env'
    _write_env_key(env_path, 'GOOGLE_REFRESH_TOKEN', refresh_token)

    # ── Confirm to the admin ─────────────────────────────────────────────────────
    return HttpResponse(
        f"<h2>✅ Google Calendar Authorized!</h2>"
        f"<p>Refresh token saved to <code>.env</code> successfully.</p>"
        f"<p><strong>Refresh Token:</strong> <code>{refresh_token}</code></p>"
        f"<p>You can now close this page. Google Meet scheduling is active.</p>"
        f"<p><strong>⚠️ Restart the Django server</strong> for the token to be loaded.</p>",
    )


def _write_env_key(env_path: Path, key: str, value: str):
    """Update or append a key=value pair in the .env file."""
    lines = []
    found = False
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.startswith(f'{key}='):
                lines[i] = f'{key}={value}\n'
                found = True
                break

    if not found:
        lines.append(f'{key}={value}\n')

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
