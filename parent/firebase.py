import os

import firebase_admin
from django.conf import settings
from firebase_admin import credentials, messaging


def initialize_firebase():
    if firebase_admin._apps:
        return

    cred_path = settings.FIREBASE_CREDENTIALS

    if not os.path.isabs(str(cred_path)):
        cred_path = settings.BASE_DIR / str(cred_path)

    cred = credentials.Certificate(str(cred_path))
    firebase_admin.initialize_app(cred)


def send_fcm_notification(token, title, body, data=None):
    initialize_firebase()

    if data is None:
        data = {}

    data = {str(key): str(value) for key, value in data.items()}

    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data,
        token=token,
    )

    return messaging.send(message)


def send_fcm_multicast(tokens, title, body, data=None):
    initialize_firebase()

    if data is None:
        data = {}

    data = {str(key): str(value) for key, value in data.items()}

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data,
        tokens=tokens,
    )

    return messaging.send_each_for_multicast(message)