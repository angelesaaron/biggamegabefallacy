"""
Shared rate-limiter instance.

Defined here (not in main.py) to avoid a circular import:
  main.py imports auth_router → auth.py would import from main.py.
Both main.py and auth.py import from here instead.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_real_ip(request):
    """
    Resolve the client IP from X-Forwarded-For when running behind a reverse
    proxy (Render, Vercel edge, etc.). Falls back to the direct remote address.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may be a comma-separated list; the leftmost is the client
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_get_real_ip)
