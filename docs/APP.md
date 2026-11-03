# Liftlog: application guide

How the app works, what each part does, and why it was built that way. Deployment
steps are in [deploy/DEPLOY-NOTES.md](deploy/DEPLOY-NOTES.md).

## Architecture

```
Browser ──HTTPS──> Nginx ─┬─ /, /assets/   → frontend/dist (React SPA; unknown paths → index.html)
                          ├─ /api/, /admin/ → Gunicorn :8000 (Django + DRF) ─┬─> PostgreSQL (data, pg_trgm)
                          ├─ /static/       → Django admin CSS/JS           └─> Redis (sessions, cache, throttles)
                          └─ /media/        → secure_link check → photo files on disk
Prometheus ─> 127.0.0.1:8000/metrics        Stripe ──signed webhook──> /api/billing/webhook/
```

| Component | Technology | Responsibility |
|---|---|---|
| HTTP server | Nginx | TLS, HTTP→HTTPS redirect, serves the SPA and photos, reverse proxy to Gunicorn, rate limiting, security headers, JSON access logs |
| Frontend | React 19 + Vite 8, Tailwind 4, React Router, TanStack Query, Recharts | Single-page app; talks to `/api/` with a session cookie |
| Application | Django 5.2 LTS + Django REST Framework on Gunicorn | REST API, auth, business logic, image processing, Stripe integration |
| Database | PostgreSQL | Users, workouts, posts, friendships, subscriptions; trigram index for exercise search |
| Cache | Redis | Login sessions, cached lookups (friend lists, exercise search, unread counts, leaderboards), rate-limit counters |
| Payments (optional) | Stripe (test mode) | Hosted checkout, subscription webhooks, billing portal |

Backend apps (`backend/apps/`):

| App | Contents |
|---|---|
| `core` | Health check, request-ID + JSON logging middleware, `Photo` model, image pipeline, URL signing, permission helpers, metrics, `cleanup_media` |
| `accounts` | Custom `User`, register/login/logout, lockout, 2FA, password reset, data export, account deletion |
| `workouts` | Exercise catalogue + custom exercises, workouts/sets, PR and progress calculations, templates, calendar |
| `social` | Friendships, posts, likes, comments, notifications, **visibility rules** |
| `billing` | `Subscription`, Stripe checkout/portal/webhooks, demo billing, `setup_stripe`, `grant_premium` |
| `insights` | Premium: analytics, body metrics, recaps (+ rendered recap image), leaderboards, challenges |

## Features

**Core**
- Register / log in / log out (username or email), private-by-default accounts, kg or lb.
- **Workout logger**: search 876 exercises (typo-tolerant), add sets with weight × reps, "last time" hints,
  repeat-last-set, timer, saved on the device until you finish (survives refresh), log past days.
- **Calendar** of your workouts (owner-only), workout detail with per-set PR badges, edit, delete.
- **Share flow**: after finishing, add a photo + caption → post with an auto-generated stats card. Skippable.
- **Feed** (you + friends), **Explore** (public accounts), profiles with Instagram-style grids, likes, comments.
- **Friends**: mutual friend requests (send / accept / decline / cancel / unfriend).
- **Notifications** for requests, likes, comments, challenges, failed payments (polled every 30 s).

**Extras**
- Personal records (heaviest set and best estimated 1RM) detected automatically; progress charts per exercise.
- Workout templates, pre-filled with the weights you used last time.
- Custom exercises (private).
- Two-factor authentication (TOTP) with one-time recovery codes.
- Password reset by email; email/password change; GDPR data export (JSON); account deletion.
- **Premium subscription** (Stripe test mode, or demo mode): advanced analytics (training heatmap, weekly sets/volume
  per muscle, 1RM trends, all-time progress), body metrics with relative strength, monthly/yearly recaps rendered as a
  shareable image, weekly friend leaderboards and head-to-head challenges.

## Who can see what (authorization)

All rules live in `apps/social/visibility.py` and are enforced by the API (the UI only mirrors them):

| Data | Visible to |
|---|---|
| Posts (and their photos, likes, comments) | the author, their friends, and everyone if the author's account is public |
| Profile header (username, avatar, bio, counts) | everyone logged in |
| Workouts, calendar, templates, progress, custom exercises, body metrics | only the owner (other users get **404**, so existence isn't revealed) |
| Leaderboards | friends who haven't opted out; weekly totals only |
| Premium endpoints | Premium users; others get **402 Payment Required** `{"code": "premium_required"}` |
| Django admin | superusers only |

Photo URLs are only handed out in API responses that already passed these checks, and
they're signed and expire (see below), so guessing a URL gets you nothing.

## Security features

| Area | How |
|---|---|
| Transport | HTTPS only (HTTP→HTTPS redirect), HSTS, secure cookies |
| Passwords | Argon2id hashing; Django validators (min 10 chars, not common, not numeric, not similar to username) |
| Sessions | Server-side in Redis; httpOnly + Secure + SameSite=Lax cookie; key rotated at login (no session fixation); logout deletes it; password change ends other sessions |
| CSRF | Token header on every write, also enforced on login/register (prevents login CSRF); Origin check |
| Brute force | Nginx `limit_req` (10/min per IP on auth endpoints) → DRF throttles (per IP / per user) → account lockout after 5 failures for 15 min (counter in Redis) |
| 2FA | TOTP (RFC 6238), ±30 s drift, a code can't be used twice (atomic compare-and-set on the time step), 10 recovery codes stored as SHA-256 hashes |
| Account enumeration | Same error for "no such user" and "wrong password"; password reset always answers the same |
| Password reset | Django's HMAC token: expires after 1 h and stops working once used |
| Uploads | Size limit (Nginx 12 MB, app 10 MB), real image decoding (JPEG/PNG/WebP only), pixel limit against decompression bombs, re-encoded to WebP so **EXIF/GPS metadata is removed** |
| Media access | URLs signed with a shared secret, verified by Nginx `secure_link`; 403 forged, 410 expired |
| Headers | CSP, X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy |
| Payments | Card data never touches our server (Stripe Checkout); webhooks verified by HMAC signature with a 5-minute replay window; event IDs stored so duplicates are ignored; the return redirect is never trusted, the session is fetched from Stripe |
| Least privilege | Gunicorn on localhost only, runs as `liftlog` under systemd sandboxing; PostgreSQL peer auth (no DB password); secrets only in a 0640 env file |
| Audit log | `liftlog.security` logger: signups, logins, failures, lockouts, 2FA changes, password resets, exports, deletions |

**Known trade-offs** (worth knowing for questions):
- A signed photo URL keeps working until it expires (6–12 h), even after unfriending or
  switching to private: the same model Instagram's CDN uses. Shorter `MEDIA_URL_TTL_SECONDS` = faster revocation, worse caching.
- `secure_link_md5` uses MD5. Forging a link still requires the secret, but it's not an HMAC.
- TOTP secrets are stored unencrypted in PostgreSQL (the database is only reachable locally by the app user).
- Per-username lockout lets an attacker temporarily lock someone's account by guessing; the lockout is short (15 min) for that reason.
- Sessions live only in Redis: restarting Redis without persistence logs everyone out.

## How the main mechanisms work

**Signed photo URLs.** `apps/core/signing.py` builds
`/media/photos/ab/<sha256>/1080.webp?e=<expiry>&s=<signature>` with
`signature = base64url(md5("<expiry><path> <secret>"))`. Nginx recomputes the same hash with
`secure_link_md5` and serves the file only if it matches and hasn't expired. The expiry is
rounded to 6-hour windows, so a photo's URL stays identical for a while and the browser
cache keeps working. In development, Django's `signed_media` view does the same check.

**Photo pipeline.** `apps/core/images.py`: size check → SHA-256 of the bytes (identical
uploads are stored once) → Pillow decodes it (rejects non-images and huge images) → apply
EXIF rotation → 1080 px version + 320 px square thumbnail → WebP quality 80 → files at
`photos/<ab>/<sha256>/`. The original is discarded. A 4 MB phone photo becomes ~200 KB.
When the last post or avatar using a photo is deleted, the files are removed (signal +
daily `cleanup_media`).

**PRs and progress.** Nothing is stored: `apps/workouts/services.py` compares each set with
the user's earlier history in SQL (`MAX(weight)`, `MAX(e1RM)` with the Epley formula
`weight × (1 + reps/30)`). Editing an old workout can't leave stale records behind.

**Rate limits and lockout.** DRF scoped throttles use Redis counters per IP (anonymous)
or per user. Login failures are additionally counted per account
(`apps/accounts/security.py`).

**Premium.** `Subscription.grants_premium()` decides access (active/trialing, or past_due for
3 days of grace; demo subscriptions expire on their date). `IsPremium` raises 402. Stripe
events update the row through `apps/billing/webhooks.py`.

**Observability.** Every request gets an ID (from Nginx's `X-Request-ID`, or generated), which
is added to every log line and echoed in the response. Logs are JSON on stdout (→ journald).
`/metrics` exposes django-prometheus metrics plus `liftlog_*` business counters, combined
across Gunicorn workers via `PROMETHEUS_MULTIPROC_DIR`.

## API overview

All endpoints are under `/api/`, use JSON, and need a session cookie unless marked public.
Errors use DRF's format (`{"detail": ...}` or `{"field": ["message"]}`); 401 = not logged in,
402 = needs Premium, 403 = not allowed / CSRF, 404 = doesn't exist *for you*, 429 = slow down.

| Endpoint | Purpose |
|---|---|
| `GET health/` (public) | DB + Redis check (200/503) |
| `GET auth/csrf/` (public) | Sets the CSRF cookie |
| `POST auth/register/`, `auth/login/`, `auth/login/2fa/`, `auth/logout/` (public) | Account and session |
| `GET/PATCH auth/me/`, `POST/DELETE auth/me/avatar/` | Own profile and settings |
| `POST auth/password/change/`, `auth/password/reset/`, `auth/password/reset/confirm/` | Passwords |
| `POST auth/2fa/setup/`, `auth/2fa/confirm/`, `auth/2fa/disable/` | Two-factor auth |
| `GET auth/me/export/`, `POST auth/me/delete/` | GDPR export / delete account |
| `GET/POST exercises/?q=&muscle=`, `GET exercises/{id}/progress/?range=90\|365\|all`, `GET exercises/{id}/last/` | Catalogue, custom exercises, progress |
| `GET/POST workouts/?from=&to=`, `GET/PATCH/DELETE workouts/{id}/`, `GET workouts/calendar/?month=`, `POST workouts/{id}/save-as-template/` | Workouts |
| `GET/POST templates/`, `POST templates/{id}/start/` | Templates |
| `POST posts/` (multipart), `GET posts/feed/`, `GET posts/explore/`, `GET/PATCH/DELETE posts/{id}/` | Posts (cursor pagination) |
| `POST/DELETE posts/{id}/like/`, `GET/POST posts/{id}/comments/`, `DELETE comments/{id}/` | Likes and comments |
| `GET users/?q=`, `GET users/{username}/`, `GET users/{username}/posts/` | People and profiles |
| `GET friends/`, `DELETE friends/{username}/`, `GET/POST friends/requests/`, `POST friends/requests/{id}/accept/`, `DELETE friends/requests/{id}/` | Friendships |
| `GET notifications/`, `GET notifications/unread-count/`, `POST notifications/read/` | Notifications |
| `GET billing/status/`, `POST billing/checkout/`, `POST billing/portal/`, `POST billing/cancel-demo/`, `POST billing/webhook/` (Stripe) | Subscription |
| `GET analytics/muscle-volume/`, `analytics/heatmap/`, `analytics/e1rm-trends/` ★ | Premium analytics |
| `GET/POST body-metrics/`, `GET body-metrics/summary/` ★ | Body metrics |
| `GET recap/?month=\|year=`, `POST recap/share/` ★ | Recaps |
| `GET leaderboards/weekly/` ★, `GET/POST challenges/` (create ★), `POST challenges/{id}/accept\|decline/` | Competition |

★ = Premium.

## Management commands

| Command | What it does |
|---|---|
| `migrate` | Create/upgrade tables (+ `pg_trgm` extension) |
| `load_exercises` | Load/refresh the 876-exercise catalogue (idempotent) |
| `collectstatic` | Copy Django admin assets to `STATIC_ROOT` |
| `createsuperuser` | Admin account for `/admin/` |
| `check --deploy` | Django's production security checklist |
| `cleanup_media [--dry-run]` | Delete unused photos and stray files (daily timer) |
| `finish_challenges` | Settle challenges that ended (daily timer) |
| `setup_stripe` | Create the Stripe product and prices (Stripe mode) |
| `grant_premium <user> --days N` | Give someone Premium without payment |

## Configuration

All settings come from environment variables; see
[deploy/liftlog.env.example](deploy/liftlog.env.example) for the full annotated list.
Local development uses `backend/dev.env` (development-only values, safe to commit).

## Local development

Requirements: Python ≥ 3.12, Node ≥ 20.19, and PostgreSQL + Redis (Docker or apt).

```bash
make services        # PostgreSQL 16 + Redis 7 in Docker   (or: make services-apt)
make setup           # venv + pip install + npm ci
make migrate seed-exercises
make backend         # Django on http://127.0.0.1:8000 (terminal 1)
make frontend        # Vite on http://localhost:5173  (terminal 2) → open this one
make check-deploy    # production security checklist
```

Vite proxies `/api` and `/media` to Django and keeps the `Host` header, so the browser
sees one origin, just like behind Nginx. In development, emails (password reset) are
printed in the backend terminal and Premium runs in demo mode.
