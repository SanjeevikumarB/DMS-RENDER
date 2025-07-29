from datetime import datetime, timedelta
from accounts.utils.jwe_utils import encrypt_jwe
from django.conf import settings
from django.utils.timezone import now

def create_access_token(user):
    current_time = now()
    payload = {
        "uid": str(user.uid),
        "type": "access",
        "access_token_version": user.access_token_version,
        "exp": (current_time + timedelta(minutes=15)).isoformat()
    }
    return encrypt_jwe(payload)

def create_refresh_token(user):
    current_time = now()
    payload = {
        "uid": str(user.uid),
        "type": "refresh",
        "access_token_version": user.access_token_version,
        "exp": (current_time + timedelta(days=7)).isoformat()
    }
    return encrypt_jwe(payload)
