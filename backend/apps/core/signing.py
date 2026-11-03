"""Signed, expiring media URLs compatible with Nginx's secure_link module.

Nginx config (docs/deploy/nginx-liftlog.conf):

    secure_link $arg_s,$arg_e;
    secure_link_md5 "$secure_link_expires$uri <MEDIA_URL_SIGNING_SECRET>";

Nginx recomputes the hash from the expiry, the path and the shared secret, and
serves the file only if it matches and the expiry is in the future. Django never
sees image requests in production. Without the secret a valid signature can't be
produced, so a URL can only come from an API response that already checked
whether the viewer may see the photo.
"""
import base64
import hashlib
import hmac
import time

from django.conf import settings


def _signature(uri, expires):
    raw = f"{expires}{uri} {settings.MEDIA_URL_SIGNING_SECRET}".encode()
    return base64.urlsafe_b64encode(hashlib.md5(raw).digest()).decode().rstrip("=")


def expiry(now=None):
    """End of the *next* TTL window.

    Every URL handed out during one window gets the same expiry, so the URL
    string stays identical and the browser cache keeps working. A URL is valid
    for between 1x and 2x the TTL.
    """
    ttl = settings.MEDIA_URL_TTL_SECONDS
    now = int(now if now is not None else time.time())
    return (now // ttl + 2) * ttl


def signed_media_url(relative_path, now=None):
    uri = f"{settings.MEDIA_URL}{relative_path}"
    expires = expiry(now)
    return f"{uri}?e={expires}&s={_signature(uri, expires)}"


def check(uri, expires, signature, now=None):
    """'ok', 'invalid' (Nginx: 403) or 'expired' (Nginx: 410), mirroring secure_link."""
    try:
        expires = int(expires)
    except (TypeError, ValueError):
        return "invalid"
    if not hmac.compare_digest(_signature(uri, expires), signature or ""):
        return "invalid"
    if expires < (now if now is not None else time.time()):
        return "expired"
    return "ok"


def photo_urls(photo):
    """Signed URLs for both sizes of a Photo (or None)."""
    if photo is None:
        return None
    return {
        "full": signed_media_url(photo.path("1080")),
        "thumb": signed_media_url(photo.path("320")),
        "width": photo.width,
        "height": photo.height,
    }
