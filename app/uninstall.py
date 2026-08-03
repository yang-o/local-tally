from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from app.config import (
    get_app_bundle_path,
    get_install_dir,
    get_legacy_data_dir,
    get_portable_data_dir,
    is_frozen,
)


def _cleanup_legacy_support_dir() -> None:
    legacy = get_legacy_data_dir()
    if legacy.exists():
        shutil.rmtree(legacy, ignore_errors=True)


def uninstall_portable_app() -> None:
    """卸载打包版：删除数据目录与程序文件，然后退出进程。"""
    if not is_frozen():
        raise RuntimeError("仅打包版支持卸载")

    install_dir = get_install_dir().resolve()
    data_dir = get_portable_data_dir().resolve()
    app_bundle = get_app_bundle_path()
    if app_bundle is not None:
        app_bundle = app_bundle.resolve()

    if sys.platform == "win32":
        _uninstall_windows(install_dir)
        return

    # macOS / 其他：先删数据与应用包，再清理旧引导目录
    if data_dir.exists():
        shutil.rmtree(data_dir, ignore_errors=True)
    if app_bundle is not None and app_bundle.exists():
        shutil.rmtree(app_bundle, ignore_errors=True)
    _cleanup_legacy_support_dir()
    sys.exit(0)


def _uninstall_windows(install_dir: Path) -> None:
    """通过临时 bat 在进程退出后删除整个程序目录。"""
    _cleanup_legacy_support_dir()

    bat_path = Path(tempfile.gettempdir()) / f"tally_uninstall_{os.getpid()}.bat"
    # 延迟删除，确保当前 exe 已退出并释放文件句柄
    bat_path.write_text(
        "\r\n".join(
            [
                "@echo off",
                "ping 127.0.0.1 -n 3 >nul",
                f'rd /s /q "{install_dir}"',
                'rd /s /q "%APPDATA%\\Tally" 2>nul',
                'del "%~f0"',
                "",
            ]
        ),
        encoding="gbk",
        errors="replace",
    )

    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags |= subprocess.CREATE_NO_WINDOW
    if hasattr(subprocess, "DETACHED_PROCESS"):
        creationflags |= subprocess.DETACHED_PROCESS

    subprocess.Popen(
        ["cmd", "/c", str(bat_path)],
        creationflags=creationflags,
        close_fds=True,
    )
    sys.exit(0)
