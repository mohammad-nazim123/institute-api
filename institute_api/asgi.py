"""
ASGI config for institute_api project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from mangum import Mangum

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'institute_api.settings')

application = get_asgi_application()

def path_rewrite_middleware(app):
    async def middleware(scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            # If the path doesn't end with a slash, we add one
            # because AWS Function URLs strip them and Django expects them.
            if not path.endswith("/"):
                scope["path"] = path + "/"
        await app(scope, receive, send)
    return middleware

handler = Mangum(path_rewrite_middleware(application))
