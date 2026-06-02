#!/usr/bin/env python3
"""Keep Appium Inspector session alive with periodic health checks and auto-recovery."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from inspector_session import (  # noqa: E402
    append_keepalive_log,
    delete_session,
    is_keepalive_running,
    keepalive_pid_path,
    load_session_info,
    save_session_info,
    session_is_healthy,
)
from project_paths import resolve_project_root  # noqa: E402
from repair_appium_session import (  # noqa: E402
    _create_session,
    _load_capabilities,
    _repair_uiautomator2_on_device,
    _server_ready,
)

PROJECT_ROOT = resolve_project_root(SCRIPT_DIR)


def _interval_seconds() -> int:
    raw = os.getenv("UIATEST_INSPECTOR_KEEPALIVE_SEC", "45").strip()
    try:
        return max(15, int(raw))
    except ValueError:
        return 45


def _recreate_inspector_session(project_root: Path, server_url: str) -> str | None:
    from inspector_session import inspector_capabilities

    info = load_session_info(project_root) or {}
    old_id = str(info.get("session_id") or "").strip()
    if old_id:
        delete_session(server_url, old_id)

    _repair_uiautomator2_on_device()
    capabilities = inspector_capabilities(_load_capabilities(project_root))
    session_id = _create_session(server_url, capabilities)
    if not session_is_healthy(server_url, session_id):
        return None

    save_session_info(
        project_root,
        {
            "server_url": server_url,
            "session_id": session_id,
            "inspector_url": f"{server_url}/inspector",
            "keepalive": True,
        },
    )
    return session_id


def run_keepalive(project_root: Path, server_url: str) -> None:
    pid_path = keepalive_pid_path(project_root)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    append_keepalive_log(project_root, f"keepalive started (pid={os.getpid()}, interval={_interval_seconds()}s)")

    try:
        while True:
            if not _server_ready(server_url):
                append_keepalive_log(project_root, "Appium server not ready; waiting...")
                time.sleep(_interval_seconds())
                continue

            info = load_session_info(project_root)
            session_id = str((info or {}).get("session_id") or "").strip()
            if not session_id:
                append_keepalive_log(project_root, "No inspector session id; recreating...")
                new_id = _recreate_inspector_session(project_root, server_url)
                if new_id:
                    append_keepalive_log(project_root, f"Recreated session: {new_id}")
                time.sleep(_interval_seconds())
                continue

            if session_is_healthy(server_url, session_id):
                time.sleep(_interval_seconds())
                continue

            append_keepalive_log(
                project_root,
                f"Session {session_id} unhealthy; recreating for Inspector...",
            )
            new_id = _recreate_inspector_session(project_root, server_url)
            if new_id:
                append_keepalive_log(
                    project_root,
                    f"Inspector session restored: {new_id} "
                    f"(re-attach in Inspector if refresh still fails)",
                )
            else:
                append_keepalive_log(project_root, "Failed to recreate inspector session")
            time.sleep(_interval_seconds())
    finally:
        pid_path.unlink(missing_ok=True)
        append_keepalive_log(project_root, "keepalive stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--server-url", default=os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723"))
    args = parser.parse_args()
    project_root = args.project_root.resolve()

    if is_keepalive_running(project_root):
        existing = int(keepalive_pid_path(project_root).read_text(encoding="utf-8").strip())
        print(f"Inspector keepalive already running (pid={existing}).")
        return

    run_keepalive(project_root, args.server_url.rstrip("/"))


if __name__ == "__main__":
    main()
