from google.oauth2 import id_token
from google.auth.transport import requests
from django.conf import settings
from rest_framework.exceptions import ValidationError

def verify_google_id_token(token):
    try:
        # Verify the token and return payload
        payload = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            audience=settings.GOOGLE_CLIENT_ID
        )
        return payload  # Includes 'email', 'name', 'picture', etc.
    except Exception as e:
        raise ValidationError("Invalid Google token.")
