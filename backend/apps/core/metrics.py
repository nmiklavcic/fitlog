"""Business metrics exposed on /metrics next to django-prometheus' HTTP/DB metrics.

Under Gunicorn these are aggregated across worker processes through
PROMETHEUS_MULTIPROC_DIR (see gunicorn.conf.py).
"""
from prometheus_client import Counter

LOGINS = Counter("liftlog_logins_total", "Login attempts by result", ["result"])
SIGNUPS = Counter("liftlog_signups_total", "Accounts created")
WORKOUTS_LOGGED = Counter("liftlog_workouts_logged_total", "Workouts saved")
POSTS_CREATED = Counter("liftlog_posts_created_total", "Posts created", ["kind"])
CHECKOUTS_STARTED = Counter("liftlog_checkouts_started_total", "Premium checkouts started", ["plan"])
STRIPE_WEBHOOKS = Counter("liftlog_stripe_webhooks_total", "Stripe webhook events received", ["type", "result"])
