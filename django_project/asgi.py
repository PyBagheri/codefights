"""
ASGI config for codefights project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')

# This should be imported after setting the DJANGO_SETTINGS_MODULE
# environment variable, as otherwise the module won't recognize it.
from django_project.websocket.asgi import websocket_application


# We don't need these yet, since we aren't
# serving HTTP requests on the ASGI version yet.
#
# from django.core.asgi import get_asgi_application
# application = get_asgi_application()


# For the moment, we only serve websocket
# requests on the ASGI version.
async def application(scope, receive, send):
    if scope['type'] == 'websocket':
        # Without setup(), some things won't work,
        # such as the CSRF middleware (things like
        # errors with translations).
        django.setup(set_prefix=True)
        
        await websocket_application(scope, receive, send)
