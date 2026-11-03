"""Gunicorn settings (`gunicorn -c gunicorn.conf.py config.wsgi`).

Every value can be overridden with an environment variable, e.g. in the
systemd unit or /etc/liftlog/liftlog.env.
"""
import glob
import multiprocessing
import os

# Only Nginx talks to Gunicorn, so listen on localhost (Prometheus scrapes it here too).
bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8000")
# Classic rule of thumb: 2 x CPU cores + 1, capped so small VMs don't run out of RAM.
workers = int(os.environ.get("GUNICORN_WORKERS", min(multiprocessing.cpu_count() * 2 + 1, 8)))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", 2))
timeout = 30  # photo uploads are processed in the request; 30 s is plenty
graceful_timeout = 30
keepalive = 5
# Restart each worker after ~1000 requests to keep memory use bounded.
max_requests = 1000
max_requests_jitter = 100
# Requests are logged by Nginx and by Django's middleware (with request IDs), not here.
accesslog = None
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
# Trust X-Forwarded-* headers only from the local Nginx.
forwarded_allow_ips = "127.0.0.1"
proc_name = "liftlog"

# --- Prometheus multiprocess mode -----------------------------------------------------
# Each worker is a separate process with its own counters. prometheus_client
# writes them to files in PROMETHEUS_MULTIPROC_DIR and /metrics adds them up.


def on_starting(server):
    path = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if path:
        os.makedirs(path, exist_ok=True)
        for stale in glob.glob(os.path.join(path, "*.db")):  # files from a previous run
            os.remove(stale)


def child_exit(server, worker):
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
