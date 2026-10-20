"""
ASGI config for MLFlowPro project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MLFlowPro.settings')

application = get_asgi_application()

# MLFlowPro: WebSocket collaboration routing
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path
from experiments.collaboration import ExperimentNotesConsumer

http_application = application
application = ProtocolTypeRouter({
    "http": http_application,
    "websocket": AllowedHostsOriginValidator(URLRouter([
        path("ws/experiment-notes/", ExperimentNotesConsumer.as_asgi()),
    ])),
})
