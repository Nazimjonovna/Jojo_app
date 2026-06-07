import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

django_asgi_app = get_asgi_application()

import socketio

from parent.middleware import JWTAuthMiddlewareStack
from parent.routing import websocket_urlpatterns
from core.socketio_server import sio


# Channels (eski WS) + Django HTTP. Socket.IO bu ProtocolTypeRouter ustiga
# o'raladi va `/socket.io/` so'rovlarini o'ziga oladi.
channels_app = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    }
)

# Socket.IO ASGI server — `/socket.io/` path uchun. Boshqa hamma yo'l
# eski Channels app'iga o'tadi (HTTP + eski WS). Migratsiya tugagach
# `channels_app` o'rniga to'g'ridan-to'g'ri `django_asgi_app`ni qo'yamiz
# va Channels'ni olib tashlaymiz.
application = socketio.ASGIApp(
    socketio_server=sio,
    other_asgi_app=channels_app,
    socketio_path="socket.io",
)