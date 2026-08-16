"""aiohttp application factory for the PWA + Telegram Mini App."""

from __future__ import annotations

from pathlib import Path

from aiohttp import web

from src.config.env import Settings
from src.web import routes

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _cors_middleware(app: web.Application):
    """Allow the frontend to be hosted on a different origin (e.g. GitHub Pages).

    ngrok/cloudflared only tunnel the backend API; the static PWA is served
    from GitHub Pages. Browser fetch() to the API therefore comes from a cross
    origin and needs CORS headers. Tighten the allowed origin in production.
    """
    import os

    allowed = os.environ.get("WEB_CORS_ORIGIN", "*")

    @web.middleware
    async def middleware(request: web.Request, handler):
        if request.method == "OPTIONS":
            resp = web.Response()
            resp.headers["Access-Control-Allow-Origin"] = allowed
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            resp.headers["Access-Control-Max-Age"] = "86400"
            return resp
        resp = await handler(request)
        resp.headers["Access-Control-Allow-Origin"] = allowed
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return resp

    return middleware


def create_web_app(settings: Settings) -> web.Application:
    app = web.Application()
    app["settings"] = settings
    app["static_dir"] = _STATIC_DIR

    app.middlewares.append(_cors_middleware(app))

    app.add_routes(routes.build_routes(_STATIC_DIR))

    app.router.add_get("/", routes.serve_index)
    app.router.add_get("/manifest.webmanifest", routes.serve_manifest)
    app.router.add_get("/sw.js", routes.serve_service_worker)
    app.router.add_get("/icon-192.png", routes.serve_icon_192)
    app.router.add_get("/icon-512.png", routes.serve_icon_512)
    app.router.add_get("/favicon.ico", routes.serve_icon_192)

    app.router.add_post("/api/auth", routes.api_auth)
    app.router.add_post("/api/whoami", routes.api_whoami)
    app.router.add_post("/api/chat", routes.api_chat)
    app.router.add_post("/api/chat/clear", routes.api_chat_clear)
    app.router.add_post("/api/settings", routes.api_settings)
    app.router.add_post("/api/keyinfo", routes.api_keyinfo)
    app.router.add_post("/api/models", routes.api_models)
    app.router.add_post("/api/models/ping", routes.api_models_ping)
    app.router.add_post("/api/favorites", routes.api_favorites)
    app.router.add_post("/api/favorites/add", routes.api_favorite_add)
    app.router.add_post("/api/favorites/remove", routes.api_favorite_remove)

    app.router.add_post("/api/admin/summary", routes.api_admin_summary)
    app.router.add_post("/api/admin/users", routes.api_admin_users)
    app.router.add_post("/api/admin/whitelist", routes.api_admin_whitelist)
    app.router.add_post("/api/admin/user", routes.api_admin_user)
    app.router.add_post("/api/admin/reset-all", routes.api_admin_reset_all)

    app.router.add_get("/admin", routes.serve_admin)
    app.router.add_get("/admin.html", routes.serve_admin)
    app.router.add_get("/sw-register.js", routes.serve_sw_register)

    return app
