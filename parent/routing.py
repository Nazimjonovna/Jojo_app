from django.urls import path

from .consumers import ParentTrackingConsumer, ChildLocationConsumer


websocket_urlpatterns = [
    path(
        "ws/parent/tracking/",
        ParentTrackingConsumer.as_asgi(),
    ),
    path(
        "ws/child/location/",
        ChildLocationConsumer.as_asgi(),
    ),
]