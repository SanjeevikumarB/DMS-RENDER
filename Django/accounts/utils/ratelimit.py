import time
from django.core.cache import cache
from django.http import JsonResponse
from functools import wraps

def custom_ratelimit(key_func, rate='5/m', block=True):
    """
    Custom rate-limiting decorator with dynamic retry-after calculation.
    Uses Django cache backend (works with database cache or Redis).
    """

    # Parse rate string: e.g., '5/m'
    num, per = rate.split('/')
    num = int(num)
    periods = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    window = periods.get(per, 60)

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            key = key_func(request)
            now = int(time.time())
            cache_key = f"rl:{key}"
            data = cache.get(cache_key, {'count': 0, 'start': now})

            # Reset if window expired
            if now - data['start'] > window:
                data = {'count': 0, 'start': now}

            data['count'] += 1
            cache.set(cache_key, data, timeout=window)

            if data['count'] > num:
                retry_after = window - (now - data['start'])
                if block:
                    return JsonResponse({
                        "detail": f"Too many requests. Retry after {retry_after} seconds.",
                        "retry_after": retry_after
                    }, status=429)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

# ✅ Key function for rate limit
def user_or_ip_key(request):
    """Generate a key based on authenticated user or IP address."""
    if request.user.is_authenticated:
        return f"user:{request.user.id}"
    return f"ip:{request.META.get('REMOTE_ADDR')}"