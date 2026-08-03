from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_APP_NAME = "物业收费登记"
BOOTSTRAP_APP_DIR = "Tally"


def get_platform_app_support_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base


def get_bootstrap_dir() -> Path:
    """引导配置固定目录（与业务数据目录分离）。"""
    path = get_platform_app_support_dir() / BOOTSTRAP_APP_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_bootstrap_path() -> Path:
    return get_bootstrap_dir() / "bootstrap.json"


def get_legacy_data_dir() -> Path:
    """旧版默认数据目录，用于迁移检测。"""
    return get_platform_app_support_dir() / BOOTSTRAP_APP_DIR
