import subprocess
import os
import aiohttp
from aiohttp import web


async def api_check_update(request: web.Request) -> web.Response:
    try:
        plugin_dir = os.path.expanduser("~/comfyui/ComfyUI/custom_nodes/comfyui-aigate")

        # 先从远程获取最新信息
        fetch_result = subprocess.run(
            ["git", "fetch"], cwd=plugin_dir, capture_output=True, text=True
        )
        
        if fetch_result.returncode != 0:
            return web.json_response(
                {
                    "code": 500,
                    "data": {},
                    "message": f"Fetch failed: {fetch_result.stderr}",
                },
                status=500,
            )

        # Get local commit hash
        local_hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=plugin_dir, capture_output=True, text=True
        )

        if local_hash_result.returncode != 0:
            return web.json_response(
                {
                    "code": 500,
                    "data": {},
                    "message": f"Failed to get local hash: {local_hash_result.stderr}",
                },
                status=500,
            )

        local_hash = local_hash_result.stdout.strip()

        # Get remote commit hash
        remote_hash_result = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            cwd=plugin_dir,
            capture_output=True,
            text=True,
        )

        if remote_hash_result.returncode != 0:
            return web.json_response(
                {
                    "code": 500,
                    "data": {},
                    "message": f"Failed to get remote hash: {remote_hash_result.stderr}",
                },
                status=500,
            )

        remote_hash = remote_hash_result.stdout.strip()

        # Compare hashes
        needs_update = local_hash != remote_hash

        return web.json_response(
            {
                "code": 200,
                "data": {
                    "needs_update": needs_update,
                    "local_hash": local_hash,
                    "remote_hash": remote_hash,
                },
                "message": "Check completed",
            }
        )

    except Exception as e:
        return web.json_response(
            {"code": 500, "data": {}, "message": f"Check failed: {str(e)}"}, status=500
        )


async def api_update_plugin(request: web.Request) -> web.Response:
    try:
        # Change to the plugin directory
        plugin_dir = os.path.expanduser("~/comfyui/ComfyUI/custom_nodes/comfyui-aigate")

        # Fetch latest changes
        fetch_result = subprocess.run(
            ["git", "fetch"], cwd=plugin_dir, capture_output=True, text=True
        )

        if fetch_result.returncode != 0:
            return web.json_response(
                {
                    "code": 500,
                    "data": {},
                    "message": f"Fetch failed: {fetch_result.stderr}",
                },
                status=500,
            )

        # Get local commit hash
        local_hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=plugin_dir, capture_output=True, text=True
        )

        if local_hash_result.returncode != 0:
            return web.json_response(
                {
                    "code": 500,
                    "data": {},
                    "message": f"Failed to get local hash: {local_hash_result.stderr}",
                },
                status=500,
            )

        local_hash = local_hash_result.stdout.strip()

        # Get remote commit hash
        remote_hash_result = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            cwd=plugin_dir,
            capture_output=True,
            text=True,
        )

        if remote_hash_result.returncode != 0:
            return web.json_response(
                {
                    "code": 500,
                    "data": {},
                    "message": f"Failed to get remote hash: {remote_hash_result.stderr}",
                },
                status=500,
            )

        remote_hash = remote_hash_result.stdout.strip()

        # Compare hashes to check if update is needed
        if local_hash != remote_hash:
            # Pull the latest changes
            pull_result = subprocess.run(
                ["git", "pull"], cwd=plugin_dir, capture_output=True, text=True
            )

            if pull_result.returncode != 0:
                return web.json_response(
                    {
                        "code": 500,
                        "data": {},
                        "message": f"Pull failed: {pull_result.stderr}",
                    },
                    status=500,
                )

            # Optionally restart the service
            # This depends on how ComfyUI is deployed
            # For example, you might send a signal to a process manager

            return web.json_response(
                {"code": 200, "data": 1, "message": "云扉插件更新成功，需要重启ComfyUI"}
            )
        else:
            return web.json_response(
                {"code": 200, "data": 2, "message": "云扉插件已经是最新版本"}
            )

    except Exception as e:
        return web.json_response(
            {"code": 500, "data": {}, "message": f"Update failed: {str(e)}"}, status=500
        )


async def api_restart_comfyui(request: web.Request) -> web.Response:
    try:
        # Execute the restart script
        restart_result = subprocess.run(
            ["/etc/waas-script/restart_comfyui.sh"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if restart_result.returncode != 0:
            return web.json_response(
                {
                    "code": 500,
                    "data": {},
                    "message": f"Restart failed: {restart_result.stderr}",
                },
                status=500,
            )

        return web.json_response(
            {"code": 200, "data": {}, "message": "ComfyUI重启命令已执行，请稍等片刻后刷新页面"}
        )

    except subprocess.TimeoutExpired:
        return web.json_response(
            {"code": 500, "data": {}, "message": "重启超时，请手动检查ComfyUI状态"}, status=500
        )
    except Exception as e:
        return web.json_response(
            {"code": 500, "data": {}, "message": f"Restart failed: {str(e)}"}, status=500
        )
