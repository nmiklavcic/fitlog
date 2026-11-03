def client_ip(request):
    """Client IP as seen by Nginx.

    Gunicorn only listens on localhost, so the request always comes through
    Nginx, which appends the real client address as the *last* X-Forwarded-For
    entry. Earlier entries are whatever the client sent and can't be trusted.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR")
