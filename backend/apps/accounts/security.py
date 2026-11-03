"""Brute-force protection and the security audit log.

Two layers stop password guessing:
1. DRF's ScopedRateThrottle limits login attempts per client IP ("login" rate).
2. This module counts failures per *account* in Redis and locks the account
   for LOGIN_LOCKOUT_SECONDS after LOGIN_FAILURE_LIMIT failures, which also
   stops slow attacks spread over many IPs.
"""
import logging

from django.conf import settings
from django.core.cache import cache

security_log = logging.getLogger("liftlog.security")


def _key(account):
    return f"login-fail:{account.strip().lower()}"


def is_locked_out(account):
    return (cache.get(_key(account)) or 0) >= settings.LOGIN_FAILURE_LIMIT


def register_failure(account):
    key = _key(account)
    # add() only sets the key (and its expiry) if it doesn't exist yet;
    # Redis INCR keeps that expiry, so the window starts at the first failure.
    cache.add(key, 0, settings.LOGIN_LOCKOUT_SECONDS)
    try:
        return cache.incr(key)
    except ValueError:  # expired between add() and incr()
        cache.set(key, 1, settings.LOGIN_LOCKOUT_SECONDS)
        return 1


def clear_failures(account):
    cache.delete(_key(account))
