"""Production ASGI entrypoint.

Railway's edge proxy and nginx both sit in front of the app and send
X-Forwarded-For / X-Forwarded-Proto. This makes the app see the real
client IP and https scheme (e.g. for redirects and the /docs page).
"""

from hypercorn.middleware import ProxyFixMiddleware

from app.main import app as fastapi_app

app = ProxyFixMiddleware(fastapi_app, mode="legacy", trusted_hops=1)
