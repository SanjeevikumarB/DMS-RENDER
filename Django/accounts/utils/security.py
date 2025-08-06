from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from accounts.models import AuthSecurityLog

def get_security_config(endpoint):
    """Fetch config for endpoint or fallback to login defaults."""
    return settings.AUTH_SECURITY.get(endpoint, settings.AUTH_SECURITY['login'])

def check_lockout(user, ip, endpoint):
    """Check if user/IP is locked and return (allowed, wait_seconds)."""
    log = AuthSecurityLog.objects.filter(
        user=user if user else None,
        ip_address=ip,
        endpoint=endpoint
    ).first()

    if log and log.locked_until and log.locked_until > timezone.now():
        wait = int((log.locked_until - timezone.now()).total_seconds())
        return False, wait
    return True, None

def record_failed_attempt(user, ip, endpoint):
    """Increment failed attempts and apply lock if threshold exceeded."""
    config = get_security_config(endpoint)
    threshold = config['FAILED_ATTEMPTS_THRESHOLD']
    lock_duration = config['LOCKOUT_DURATION_MINUTES']

    log, _ = AuthSecurityLog.objects.get_or_create(
        user=user if user else None,
        ip_address=ip,
        endpoint=endpoint
    )

    log.failed_attempts += 1
    if log.failed_attempts >= threshold:
        log.locked_until = timezone.now() + timedelta(minutes=lock_duration)
        log.failed_attempts = 0  # Reset after lock
    log.save()

def reset_failed_attempts(user, ip, endpoint):
    """Clear attempts after success."""
    AuthSecurityLog.objects.filter(user=user, ip_address=ip, endpoint=endpoint).delete()
