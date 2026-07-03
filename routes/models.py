from typing import Dict, List, Any
import os
from aiohttp import web
from os import path
import glob
import shutil
import subprocess


def _collect_ineffective_symlinks(root_path: str) -> Dict[str, Any]:
    details: List[Dict[str, Any]] = []
    for dirpath, _, filenames in os.walk(root_path):
        for f in filenames:
            entry_path = os.path.join(dirpath, f)
            if os.path.islink(entry_path):
                try:
                    link_target = os.readlink(entry_path)
                except OSError:
                    link_target = ""

                resolved_target = (
                    os.path.realpath(os.path.join(dirpath, link_target))
                    if not os.path.isabs(link_target)
                    else os.path.realpath(link_target)
                )

                is_effective = bool(resolved_target and os.path.exists(resolved_target))
                if not is_effective:
                    details.append(
                        {
                            "name": path.relpath(entry_path, root_path),
                            "target_path": (
                                resolved_target if link_target else link_target
                            ),
                        }
                    )

    return {"details": details}


async def api_get_ineffective_models(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    root_paths: List[str] = payload.get("rootPaths", [])

    data: Dict[str, Any] = {}
    for root in root_paths:
        data[root] = _collect_ineffective_symlinks(root)

    return web.json_response(
        {
            "code": 200,
            "data": data,
            "message": "success",
        }
    )


def _clear_models(paths: List[str]):
    for p in paths:
        if not path.lexists(p):
            continue

        try:
            if path.islink(p):
                os.unlink(p)
            elif path.isfile(p):
                os.remove(p)
            elif path.isdir(p):
                shutil.rmtree(p)
            else:
                # Fallback: attempt unlink for other special types
                os.unlink(p)
        except Exception:
            pass


async def api_clear_models(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"code": 400, "message": "invalid json"}, status=400)

    paths: List[str] = payload.get("paths", [])
    if not isinstance(paths, list):
        return web.json_response({"code": 400, "message": "bad request"}, status=400)

    _clear_models(paths)

    return web.json_response(
        {
            "code": 200,
            "data": {},
            "message": "success",
        }
    )


"""
Create symlinks for files under a source path into a destination path.

Behavior:
- If `src_root` is a single file: creates a symlink at
    `dst_path/dest_rel_root` when provided, otherwise at `dst_path/<basename(src_root)>`.
- If `src_root` is a directory: mirrors its structure under
    `dst_path/dest_rel_root` when provided, otherwise under `dst_path/<basename(src_root)>`,
    and creates symlinks only for files (directories are created as needed).
- Directory traversal does not follow directory symlinks (`followlinks=False`).

Return stats:
- `total_files`: number of files discovered (or 1 for single-file input)
- `succeeded`: symlinks created successfully
- `failed`: symlink creations that raised errors
- `skipped`: destinations that already existed (file or symlink)
"""


def _link_files_under_root(
    src_root: str, dst_path: str, dest_rel_root: str | None = None
) -> Dict[str, Any]:
    stats: Dict[str, Any] = {"total_files": 0, "succeeded": 0, "failed": 0, "skipped": 0, "failed_items": []}

    if not path.exists(src_root):
        return stats

    if path.isfile(src_root):
        stats["total_files"] += 1
        try:
            if dest_rel_root:
                dst_file = path.join(dst_path, dest_rel_root)
                os.makedirs(path.dirname(dst_file), exist_ok=True)
            else:
                os.makedirs(dst_path, exist_ok=True)
                dst_file = path.join(dst_path, path.basename(src_root))
            if path.exists(dst_file) or path.islink(dst_file):
                stats["skipped"] += 1
                return stats
            os.symlink(src_root, dst_file)
            stats["succeeded"] += 1
        except Exception:
            stats["failed"] += 1
            stats["failed_items"].append(dest_rel_root or path.basename(src_root))
        return stats

    if not path.isdir(src_root):
        return stats

    if dest_rel_root:
        root_target = path.join(dst_path, dest_rel_root)
    else:
        base_name = path.basename(src_root.rstrip(path.sep))
        root_target = path.join(dst_path, base_name)

    try:
        os.makedirs(root_target, exist_ok=True)
    except Exception:
        # root_target creation failed, count all files as failed
        for dirpath, _, filenames in os.walk(src_root, followlinks=False):
            rel_dir = path.relpath(dirpath, src_root)
            stats["total_files"] += len(filenames)
            stats["failed"] += len(filenames)
            for f in filenames:
                rel_file = path.join(rel_dir, f) if rel_dir != "." else f
                stats["failed_items"].append(rel_file)
        return stats

    for dirpath, _, filenames in os.walk(src_root, followlinks=False):
        rel_dir = path.relpath(dirpath, src_root)
        target_dir = path.join(root_target, rel_dir) if rel_dir != "." else root_target

        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception:
            # target_dir creation failed, skip files in this directory
            stats["failed"] += len(filenames)
            for f in filenames:
                rel_file = path.join(rel_dir, f) if rel_dir != "." else f
                stats["failed_items"].append(rel_file)
            continue

        for f in filenames:
            stats["total_files"] += 1
            src_file = path.join(dirpath, f)
            dst_file = path.join(target_dir, f)

            if path.exists(dst_file) or path.islink(dst_file):
                stats["skipped"] += 1
                continue

            try:
                os.symlink(src_file, dst_file)
                stats["succeeded"] += 1
            except Exception:
                stats["failed"] += 1
                rel_file = path.join(rel_dir, f) if rel_dir != "." else f
                stats["failed_items"].append(rel_file)

    return stats


async def api_sync_models(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"code": 400, "message": "invalid json"}, status=400)

    model_root = payload.get("rootPath", "")
    models = payload.get("models", [])
    dst_path = payload.get("dstPath", "")

    if not model_root or not isinstance(models, list) or not dst_path:
        return web.json_response({"code": 400, "message": "bad request"}, status=400)

    if not path.exists(model_root) or not path.isdir(model_root):
        return web.json_response(
            {"code": 400, "message": "rootPath must be an existing directory"},
            status=400,
        )

    if not path.exists(dst_path):
        try:
            os.makedirs(dst_path, exist_ok=True)
        except Exception as e:
            return web.json_response({"code": 500, "message": str(e)}, status=500)

    result: Dict[str, Dict[str, int]] = {}
    for name in models:
        norm_name = name.lstrip("/") if isinstance(name, str) else name
        src_root = path.join(model_root, norm_name)
        dest_rel_root = norm_name
        stats = _link_files_under_root(src_root, dst_path, dest_rel_root=dest_rel_root)
        key = norm_name if norm_name.endswith(path.sep) else norm_name + path.sep
        result[key] = stats

    return web.json_response(
        {
            "code": 200,
            "data": {
                "modelRootPath": model_root,
                "result": result,
            },
            "message": "success",
        }
    )


def _exec_shell(script_path: str, args: List[str] | None) -> bool:
    if not isinstance(script_path, str) or not script_path:
        return False
    if args is not None and not isinstance(args, list):
        return False

    if not path.exists(script_path):
        return False

    # Invoke via bash to avoid executable-bit or shebang issues
    bash = "/bin/bash" if path.exists("/bin/bash") else "bash"
    cmd = [bash, script_path] + ([str(a) for a in args] if args else [])
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except Exception:
        return False


async def api_refresh_models(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response(
            {"code": 400, "data": {}, "message": "invalid request"}, status=400
        )

    script_path = payload.get("shellPath", "")
    args = payload.get("args", None)

    # Validate script exists before executing
    if not script_path or not path.exists(script_path):
        return web.json_response(
            {"code": 400, "data": {}, "message": "shellPath not found"},
            status=400,
        )

    success = _exec_shell(script_path, args)

    if success:
        return web.json_response({"code": 200, "data": {}, "message": "success"})
    else:
        return web.json_response(
            {"code": 500, "data": {}, "message": "fail"}, status=500
        )


async def api_get_envs(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response(
            {"code": 400, "data": {}, "message": "invalid request"}, status=400
        )

    envs = payload.get("envs", [])
    if not isinstance(envs, list):
        return web.json_response(
            {"code": 400, "data": {}, "message": "bad request"}, status=400
        )

    result: Dict[str, str] = {}
    for key in envs:
        name = str(key) if key is not None else ""
        if not name:
            continue
        result[name] = os.environ.get(name, "")

    return web.json_response({"code": 200, "data": result, "message": "success"})
