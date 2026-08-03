from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_APP_NAME = "物业收费登记"
BOOTSTRAP_APP_DIR = "Tally"


def is_frozen() -> bool:
    """是否为 PyInstaller 打包后的可执行程序。"""
    return bool(getattr(sys, "frozen", False))


def get_platform_app_support_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base


def get_install_dir() -> Path:
    """程序安装/解压目录。

    - Windows 打包版：Tally.exe 所在目录
    - macOS 打包版：Tally.app 所在目录
    - 开发模式：当前工作目录
    """
    if not is_frozen():
        return Path.cwd()
    exe = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        for parent in exe.parents:
            if parent.name.endswith(".app"):
                return parent.parent
    return exe.parent


def get_app_bundle_path() -> Path | None:
    """macOS 下返回 .app 包路径；其他情况返回 None。"""
    if not is_frozen() or sys.platform != "darwin":
        return None
    exe = Path(sys.executable).resolve()
    for parent in exe.parents:
        if parent.name.endswith(".app"):
            return parent
    return None


def get_portable_data_dir() -> Path:
    """打包版固定数据目录：程序目录下的 data。"""
    return get_install_dir() / "data"


def get_bootstrap_dir() -> Path:
    """引导配置目录。打包版放入 data；开发版使用系统 Application Support。"""
    if is_frozen():
        path = get_portable_data_dir()
    else:
        path = get_platform_app_support_dir() / BOOTSTRAP_APP_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_bootstrap_path() -> Path:
    return get_bootstrap_dir() / "bootstrap.json"


def get_legacy_data_dir() -> Path:
    """旧版默认数据目录，用于迁移检测。"""
    return get_platform_app_support_dir() / BOOTSTRAP_APP_DIR
