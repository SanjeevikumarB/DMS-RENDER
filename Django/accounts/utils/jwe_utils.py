# utils/jwe_utils.py
import json
from jose import jwe
from django.conf import settings

# JWE uses compact serialization and AES GCM for encryption
JWE_ALG = "dir"              # direct encryption using a shared symmetric key
JWE_ENC = "A256GCM"          # AES-GCM using 256-bit key

def encrypt_jwe(payload: dict) -> str:
    """
    Encrypts the given payload dictionary into a JWE string.
    """
    secret_key = settings.JWE_SECRET_KEY.encode()
    json_payload = json.dumps(payload).encode()
    token = jwe.encrypt(json_payload, secret_key, algorithm=JWE_ALG, encryption=JWE_ENC)
    return token.decode()

def decrypt_jwe(token: str) -> dict:
    """
    Decrypts the given JWE token back to a dictionary payload.
    Raises exception if token is invalid or expired.
    """
    secret_key = settings.JWE_SECRET_KEY.encode()
    decrypted = jwe.decrypt(token.encode(), secret_key)
    payload = json.loads(decrypted.decode())
    return payload
