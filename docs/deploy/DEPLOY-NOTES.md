# Deploying Liftlog: what the app expects

This is a checklist of everything a server needs to run Liftlog, in the order it has to
happen. It is **not** a Vagrantfile or cloud-config: turning these steps into
provisioning code (Vagrant + cloud-init) is the homework. The example config files
next to this document (`nginx/`, `systemd/`, `liftlog.env.example`) were tested
against the real app.

Paths used below (change them if you like, but consistently):

| Path | What |
|---|---|
| `/opt/liftlog` | Git checkout (`backend/`, `frontend/`) |
| `/opt/liftlog/backend/.venv` | Python virtualenv |
| `/opt/liftlog/frontend/dist` | Built React app, served by Nginx |
| `/etc/liftlog/liftlog.env` | Configuration and secrets (root:liftlog, 0640) |
| `/var/lib/liftlog/media` | Uploaded photos (liftlog:www-data, 2750) |
| `/var/lib/liftlog/static` | Django admin CSS/JS (`collectstatic`) |

## 1. Packages (apt)

```bash
apt-get update
apt-get install -y nginx postgresql redis-server python3-venv git certbot
```

- **Nginx must have the `secure_link` module** (signed photo URLs). Ubuntu 24.04's and
  newer `nginx` packages include it. On Ubuntu 22.04 install `nginx-extras` instead of
  `nginx`. Check: `nginx -V 2>&1 | grep -o with-http_secure_link_module` (or
  `strings $(which nginx) | grep -c secure_link`).
- **Node.js ≥ 20.19** is needed only to *build* the frontend. Ubuntu 24.04's apt
  `nodejs` is 18 (too old): add the NodeSource apt repository, or build the frontend
  somewhere else (e.g. CI) and copy `frontend/dist/` to the server. No Node at runtime.
- PostgreSQL ≥ 14 and Redis ≥ 6 work (tested with 14 / 6; Ubuntu 24.04 ships 16 / 7).
- Monitoring (optional, all apt-installable on Ubuntu): `prometheus`,
  `prometheus-node-exporter`, `prometheus-postgres-exporter`,
  `prometheus-redis-exporter`, `prometheus-nginx-exporter`; Grafana and Loki/Alloy from
  Grafana's apt repository.

> cloud-init tip: `packages:` are installed before `runcmd:` runs, but `write_files:` runs
> *before* packages are installed. Files that belong to package-created users/dirs (e.g.
> `/etc/nginx/...` owned by root is fine, but anything owned by `liftlog`) must be
> written or `chown`ed in `runcmd`, or with `defer: true` on the `write_files` entry.

## 2. System user and folders

```bash
useradd --system --home /opt/liftlog --shell /usr/sbin/nologin liftlog
install -d -o liftlog -g liftlog /opt/liftlog
install -d -o root -g liftlog -m 750 /etc/liftlog
install -d -o liftlog -g www-data -m 2750 /var/lib/liftlog/media   # setgid: Nginx (www-data) can read new files
install -d -o liftlog -g liftlog -m 755 /var/lib/liftlog/static
```

## 3. PostgreSQL

The app connects over the Unix socket with **peer authentication**: the OS user
`liftlog` becomes the database role `liftlog`, so there is no DB password to manage.

```bash
sudo -u postgres createuser liftlog
sudo -u postgres createdb -O liftlog liftlog
```

The first migration runs `CREATE EXTENSION pg_trgm` (fuzzy exercise search). It's a
"trusted" extension since PostgreSQL 13, so the database owner may create it: no
superuser needed. PostgreSQL listens only on localhost by default; keep it that way.

## 4. Redis

Redis holds sessions, the cache and rate-limit counters. Defaults (bind 127.0.0.1,
protected mode) are fine. Recommended in `/etc/redis/redis.conf`:

- `requirepass <secret>`, then `REDIS_URL=redis://:<secret>@127.0.0.1:6379/0`
- `maxmemory 256mb` and `maxmemory-policy volatile-lru` (every key we write has a TTL)
- `appendonly yes` if users shouldn't be logged out when Redis restarts

## 5. Code and Python dependencies

```bash
git clone <repo> /opt/liftlog        # or copy the files; owned by liftlog
cd /opt/liftlog/backend
sudo -u liftlog python3 -m venv .venv
sudo -u liftlog .venv/bin/pip install -r requirements.txt
```

## 6. Configuration

Copy `docs/deploy/liftlog.env.example` to `/etc/liftlog/liftlog.env`
(`root:liftlog`, mode `0640`) and fill in at least `DJANGO_SECRET_KEY`,
`MEDIA_URL_SIGNING_SECRET`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` and
`PUBLIC_BASE_URL`. Generate secrets with
`python3 -c 'import secrets; print(secrets.token_urlsafe(50))'`.
With `DJANGO_DEBUG=0`, the app refuses to start without the two secrets.

## 7. Database schema, data and static files

Run as `liftlog` with the env file loaded:

```bash
cd /opt/liftlog/backend
run() { sudo -u liftlog bash -c "set -a; . /etc/liftlog/liftlog.env; set +a; .venv/bin/python manage.py $*"; }
run migrate --noinput
run load_exercises          # 876 exercises; safe to re-run
run collectstatic --noinput
run check --deploy          # only W005/W021 (HSTS subdomains/preload) are expected
run createsuperuser         # interactive; or set DJANGO_SUPERUSER_* env vars and add --noinput
```

## 8. Frontend build

```bash
cd /opt/liftlog/frontend
npm ci
npm run build               # -> dist/ (about 2 s)
```

## 9. Services (systemd)

```bash
cp docs/deploy/systemd/liftlog-*.service docs/deploy/systemd/liftlog-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now liftlog-gunicorn liftlog-maintenance.timer
curl -s http://127.0.0.1:8000/api/health/     # {"status": "ok", ...}
```

- `liftlog-gunicorn.service` runs Gunicorn on `127.0.0.1:8000` as `liftlog`, sandboxed
  (`ProtectSystem=strict`; it can only write `/var/lib/liftlog/media`).
  `systemctl reload liftlog-gunicorn` restarts the workers gracefully after a code update.
- `liftlog-maintenance.timer` runs `cleanup_media` and `finish_challenges` daily.

## 10. Nginx + HTTPS

```bash
cp docs/deploy/nginx/liftlog-proxy.conf docs/deploy/nginx/liftlog-security-headers.conf /etc/nginx/snippets/
install -m 640 docs/deploy/nginx/liftlog.conf /etc/nginx/sites-available/liftlog   # contains a secret
# edit: server_name, certificate paths, CHANGE_ME_MEDIA_SIGNING_SECRET (= MEDIA_URL_SIGNING_SECRET)
ln -s /etc/nginx/sites-available/liftlog /etc/nginx/sites-enabled/liftlog
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

**Certificates**
- Public hostname (e.g. your `devops-sk-XX.lrk.si` VM): a valid Let's Encrypt certificate:
  `install -d /var/www/letsencrypt && certbot certonly --webroot -w /var/www/letsencrypt -d <host>`
  (port 80 must be reachable). Renewal is automatic (`certbot.timer`); add
  `--deploy-hook "systemctl reload nginx"`.
- Local Vagrant VM: Let's Encrypt can't reach it. Use a self-signed certificate
  (`openssl req -x509 ...`) or `mkcert`. With port forwarding (e.g. host 8443 → guest
  443) open `https://localhost:8443` directly: the HTTP→HTTPS redirect goes to port 443.
  The proxy snippet forwards `Host` *with* the port, so logins work on forwarded ports;
  just put `localhost` in `DJANGO_ALLOWED_HOSTS`.

## 11. Firewall

```bash
ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw --force enable
```

Only 22/80/443 are needed. Gunicorn (8000), PostgreSQL (5432) and Redis (6379) listen
on localhost only.

## 12. Monitoring and logs

**Prometheus**: scrape the app (and exporters) locally:

```yaml
scrape_configs:
  - job_name: liftlog
    static_configs: [{ targets: ["127.0.0.1:8000"] }]   # /metrics (blocked publicly by Nginx)
  - job_name: node
    static_configs: [{ targets: ["127.0.0.1:9100"] }]
```

Interesting metrics: `django_http_requests_latency_seconds_by_view_method`,
`django_http_responses_total_by_status_view_method`, `django_db_execute_total`,
`liftlog_logins_total{result="failure|locked|success|2fa_required"}`,
`liftlog_signups_total`, `liftlog_workouts_logged_total`, `liftlog_posts_created_total`,
`liftlog_checkouts_started_total`, `liftlog_stripe_webhooks_total`. For
`prometheus-nginx-exporter`, enable `stub_status` on a localhost-only location.

**Logs**: everything is structured JSON.
- App: `journalctl -u liftlog-gunicorn -o cat | jq` (requests, `liftlog.security`
  events such as `login_failed`/`login_locked`/`two_factor_failed`, billing, errors).
- Nginx: `/var/log/nginx/liftlog.access.log` (JSON, one line per request).
- Both carry the same `request_id`, so one request can be followed from Nginx into Django.
- Ship them to Loki with Grafana Alloy (journald + file sources) and alert on, for
  example, a spike of `login_failed` or HTTP 5xx.

**Uptime**: `GET /api/health/` returns 200, or 503 if PostgreSQL or Redis is down.

## 13. Payments (optional)

Without Stripe keys the app runs in **demo billing** mode (Upgrade = 30 free days).
For Stripe **test mode**:

1. Create a free Stripe account; copy the test secret key (`sk_test_...`) into
   `STRIPE_SECRET_KEY`.
2. `run setup_stripe`: creates the product and the monthly/yearly prices (safe to re-run).
3. Webhook endpoint `https://<host>/api/billing/webhook/` (Stripe dashboard → Developers →
   Webhooks) with events `checkout.session.completed`,
   `customer.subscription.created`, `customer.subscription.updated`,
   `customer.subscription.deleted`, `invoice.payment_failed`. Put its signing secret
   (`whsec_...`) into `STRIPE_WEBHOOK_SECRET`.
   For a VM Stripe can't reach (local Vagrant), use the Stripe CLI instead:
   `stripe listen --forward-to https://localhost:8443/api/billing/webhook/ --skip-verify`
   and use the `whsec_...` it prints.
4. Enable the Customer Portal in the Stripe dashboard (Settings → Billing → Customer portal).
5. Test card: `4242 4242 4242 4242`, any future date, any CVC.

## Updating to a new version

```bash
cd /opt/liftlog && sudo -u liftlog git pull
cd backend && sudo -u liftlog .venv/bin/pip install -r requirements.txt
run migrate --noinput && run collectstatic --noinput
cd ../frontend && npm ci && npm run build
systemctl reload liftlog-gunicorn
```
