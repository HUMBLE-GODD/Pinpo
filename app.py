"""
Vercel Serverless Entrypoint for Pinpo.
Serves the interactive legal-tech viewer and canonical transcript files.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(BASE_DIR, "app")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/").lstrip("/")
    
    # Handle root, /app, or direct asset paths
    if not path or path == "app":
        target = os.path.join(APP_DIR, "index.html")
    elif path.startswith("app/"):
        target = os.path.join(BASE_DIR, path)
    else:
        target = os.path.join(APP_DIR, path)
        if not os.path.exists(target):
            target = os.path.join(BASE_DIR, path)

    # If the requested file exists, serve it
    if os.path.exists(target) and os.path.isfile(target):
        ext = os.path.splitext(target)[1].lower()
        content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
        with open(target, "rb") as f:
            data = f.read()
        start_response("200 OK", [
            ("Content-Type", content_type),
            ("Content-Length", str(len(data))),
            ("Cache-Control", "public, max-age=3600"),
        ])
        return [data]

    # Fallback to app/index.html (SPA routing)
    fallback = os.path.join(APP_DIR, "index.html")
    with open(fallback, "rb") as f:
        data = f.read()
    start_response("200 OK", [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(data))),
    ])
    return [data]


# Aliases for WSGI / ASGI compatibility with Vercel runtimes
handler = app
application = app
