import os.path as path
from aiohttp import web
import server

from .routes import (
    models,
    proxy,
    update,
)

browser_path = path.dirname(__file__)
browser_app = web.Application()
browser_app.add_routes(
    [
        web.static("/web", path.join(browser_path, "web/dist")),
        web.post("/models/ineffective", models.api_get_ineffective_models),
        web.post("/models/sync", models.api_sync_models),
        web.post("/models/clear", models.api_clear_models),
        web.post("/models/refresh", models.api_refresh_models),
        web.post("/models/envs", models.api_get_envs),
        web.get("/proxy/{tail:.*}", proxy.api_proxy),
        web.post("/update/check-update", update.api_check_update),
        web.post("/update/update", update.api_update_plugin),
        web.post("/update/restart", update.api_restart_comfyui),
    ]
)
server.PromptServer.instance.app.add_subapp("/browser/", browser_app)

WEB_DIRECTORY = "web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
