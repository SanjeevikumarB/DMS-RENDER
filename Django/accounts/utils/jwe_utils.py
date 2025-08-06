from jwcrypto import jwk, jwe
import json
import base64
from django.conf import settings

def _get_secret_key():
    key_bytes = base64.urlsafe_b64decode(settings.JWE_SECRET_KEY)
    if len(key_bytes) != 32:
        raise ValueError("JWE_SECRET_KEY must decode to 32 bytes.")
    return jwk.JWK(kty='oct', k=base64.urlsafe_b64encode(key_bytes).decode())

def encrypt_jwe(payload: dict) -> str:
    key = _get_secret_key()
    plaintext = json.dumps(payload)
    protected_header = {
        "alg": "dir",
        "enc": "A256GCM"
    }
    token = jwe.JWE(plaintext.encode(), protected=protected_header)
    token.add_recipient(key)
    return token.serialize(compact=True)

def decrypt_jwe(token: str) -> dict:
    key = _get_secret_key()
    decrypted = jwe.JWE()
    decrypted.deserialize(token, key=key)
    return json.loads(decrypted.payload)
