"""Time-based one-time passwords (RFC 6238), as used by Google Authenticator, Aegis, 1Password...

The server and the app share a random secret. Every 30 seconds both compute
HMAC-SHA1(secret, current 30 s step) truncated to 6 digits; matching codes
prove the user holds the device with the secret.
"""
import hashlib
import hmac
import secrets
import time

import pyotp
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

ISSUER = "Liftlog"
STEP_SECONDS = 30
RECOVERY_CODE_COUNT = 10


def new_secret():
    return pyotp.random_base32()


def provisioning_uri(secret, username):
    """otpauth:// URI the authenticator app scans from a QR code."""
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=ISSUER)


def matching_step(secret, code, now=None):
    """The 30 s step the code belongs to (allowing +/-1 step of clock drift), or None."""
    code = (code or "").strip().replace(" ", "")
    if not (len(code) == 6 and code.isdigit()):
        return None
    totp = pyotp.TOTP(secret)
    current = int((now if now is not None else time.time()) // STEP_SECONDS)
    for step in (current - 1, current, current + 1):
        if hmac.compare_digest(totp.generate_otp(step), code):
            return step
    return None


def verify_code(user, code):
    """Check a TOTP code and refuse to accept the same code twice (replay protection)."""
    step = matching_step(user.totp_secret, code)
    if step is None:
        return False
    # Atomic compare-and-set: only one request can "use" a given time step.
    updated = (
        get_user_model()
        .objects.filter(pk=user.pk)
        .filter(Q(totp_last_step__isnull=True) | Q(totp_last_step__lt=step))
        .update(totp_last_step=step)
    )
    return updated == 1


def _hash_recovery_code(code):
    normalised = code.strip().lower().replace("-", "").replace(" ", "")
    return hashlib.sha256(normalised.encode()).hexdigest()


def generate_recovery_codes():
    """Return (plaintext codes to show once, hashes to store).

    The codes are 48 random bits each, so a fast hash (SHA-256) is enough;
    slow hashes like Argon2 are for low-entropy, human-chosen passwords.
    """
    codes = ["-".join(secrets.token_hex(2) for _ in range(3)) for _ in range(RECOVERY_CODE_COUNT)]
    return codes, [_hash_recovery_code(code) for code in codes]


def use_recovery_code(user, code):
    """Consume a recovery code (each one works only once)."""
    digest = _hash_recovery_code(code or "")
    with transaction.atomic():
        locked = get_user_model().objects.select_for_update().get(pk=user.pk)
        if digest not in locked.recovery_codes:
            return False
        locked.recovery_codes = [c for c in locked.recovery_codes if c != digest]
        locked.save(update_fields=["recovery_codes"])
    user.recovery_codes = locked.recovery_codes
    return True
