"""Pinned local H3 runtime preflight."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from pipeline.digest import sha256_file


class PreflightError(RuntimeError):
    pass


def _local_endpoint(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise PreflightError("H3 endpoint must use HTTP on localhost")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise PreflightError("H3 endpoint may not include credentials, query or fragment")
    return value.rstrip("/")


def _default_git_head(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PreflightError(f"cannot read git HEAD for {path}: {result.stderr.strip()}")
    return result.stdout.strip()


def verify_runtime(
    lock_path: Path,
    *,
    endpoint: str | None = None,
    check_hashes: bool = False,
    fetch_json: Callable[[str], dict] | None = None,
    git_head: Callable[[Path], str] | None = None,
) -> dict:
    data = json.loads(lock_path.resolve(strict=True).read_text())
    if data.get("schema_version") != 1:
        raise PreflightError("runtime lock schema_version must be 1")
    runtime_endpoint = _local_endpoint(endpoint or str(data.get("endpoint", "")))

    if fetch_json is None:
        def default_fetch(path: str) -> dict:
            with urlopen(runtime_endpoint + path, timeout=60) as response:
                return json.load(response)

        fetcher = default_fetch
    else:
        fetcher = fetch_json

    git_reader = git_head or _default_git_head
    core = data.get("comfyui")
    if not isinstance(core, dict):
        raise PreflightError("runtime lock is missing comfyui")
    core_path = Path(str(core.get("path", ""))).resolve(strict=True)
    expected_core = str(core.get("commit", ""))
    actual_core = git_reader(core_path)
    if actual_core != expected_core:
        raise PreflightError(f"ComfyUI commit drift: expected {expected_core}, got {actual_core}")

    plugin_checks = []
    for plugin in data.get("plugins", []):
        plugin_path = Path(str(plugin["path"])).resolve(strict=True)
        expected = str(plugin["commit"])
        actual = git_reader(plugin_path)
        if actual != expected:
            raise PreflightError(
                f"plugin commit drift for {plugin['name']}: expected {expected}, got {actual}"
            )
        plugin_checks.append({"name": plugin["name"], "commit": actual})

    model_checks = []
    for model in data.get("models", []):
        model_path = Path(str(model["path"])).resolve(strict=True)
        actual_size = model_path.stat().st_size
        expected_size = int(model["size"])
        if actual_size != expected_size:
            raise PreflightError(
                f"model size drift for {model['name']}: expected {expected_size}, got {actual_size}"
            )
        item = {"name": model["name"], "size": actual_size}
        if check_hashes:
            expected_hash = str(model.get("sha256", ""))
            actual_hash = sha256_file(model_path)
            if actual_hash != expected_hash:
                raise PreflightError(
                    f"model hash drift for {model['name']}: expected {expected_hash}, got {actual_hash}"
                )
            item["sha256"] = actual_hash
        model_checks.append(item)

    system_stats = fetcher("/system_stats")
    actual_version = str(system_stats.get("system", {}).get("comfyui_version", ""))
    expected_version = str(core.get("version", ""))
    if actual_version != expected_version:
        raise PreflightError(
            f"ComfyUI version drift: expected {expected_version}, got {actual_version}"
        )
    object_info = fetcher("/object_info")
    missing_nodes = [name for name in data.get("required_nodes", []) if name not in object_info]
    if missing_nodes:
        raise PreflightError(f"missing required nodes: {', '.join(missing_nodes)}")
    queue = fetcher("/queue")

    return {
        "status": "PASS",
        "endpoint": runtime_endpoint,
        "comfyui": {"version": actual_version, "commit": actual_core},
        "plugins": plugin_checks,
        "models": model_checks,
        "required_nodes": len(data.get("required_nodes", [])),
        "queue": {
            "running": len(queue.get("queue_running", [])),
            "pending": len(queue.get("queue_pending", [])),
        },
        "hashes_checked": check_hashes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the pinned local H3 runtime")
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--endpoint")
    parser.add_argument("--hash", action="store_true", dest="check_hashes")
    args = parser.parse_args(argv)
    report = verify_runtime(
        args.lock,
        endpoint=args.endpoint,
        check_hashes=args.check_hashes,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
