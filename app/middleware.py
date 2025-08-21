# middleware.py
from fastapi import Request
from fastapi.responses import JSONResponse
import httpx


DJANGO_VERIFY_URL = "http://localhost:8000/api/v1/auth/verify-token/"  
# 👆 replace with your Django server URL


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        auth_header = request.headers.get("authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            response = JSONResponse(
                {"detail": "Authorization header missing or invalid"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        token = auth_header.split(" ")[1]

        # Call Django to verify token
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(DJANGO_VERIFY_URL, json={"access_token": token})
            except Exception:
                response = JSONResponse(
                    {"detail": "Auth service unreachable"},
                    status_code=503,
                )
                await response(scope, receive, send)
                return

        if resp.status_code != 200:
            response = JSONResponse(resp.json(), status_code=resp.status_code)
            await response(scope, receive, send)
            return

        data = resp.json()
        if not data.get("valid"):
            response = JSONResponse(
                {"detail": "Invalid or expired token"}, status_code=401
            )
            await response(scope, receive, send)
            return

        # Attach user info
        scope["state"]["user"] = {
            "id": data.get("user_id"),
            "email": data.get("email"),
        }

        await self.app(scope, receive, send)
