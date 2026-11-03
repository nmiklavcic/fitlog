from rest_framework import authentication


class SessionAuthentication(authentication.SessionAuthentication):
    """DRF's session auth (with CSRF enforcement), but answering 401 instead of 403.

    DRF only sends 401 when the auth class provides a WWW-Authenticate value.
    A distinct 401 lets the frontend tell "not logged in" apart from
    "logged in but not allowed" (403) and "needs Premium" (402).
    """

    def authenticate_header(self, request):
        return 'Session realm="api"'
