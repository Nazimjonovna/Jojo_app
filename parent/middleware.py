from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication


@database_sync_to_async
def get_user_from_token(raw_token):
    if not raw_token:
        return AnonymousUser()

    try:
        jwt_authentication = JWTAuthentication()
        validated_token = jwt_authentication.get_validated_token(raw_token)
        user = jwt_authentication.get_user(validated_token)
        return user
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)

        token = None

        if "token" in query_params:
            token = query_params["token"][0]

        scope["user"] = await get_user_from_token(token)

        return await self.inner(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)