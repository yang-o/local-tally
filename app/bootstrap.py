from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from app.config import DEFAULT_APP_NAME, get_bootstrap_path, get_legacy_data_dir


@dataclass
class BootstrapData:
    app_name: str = DEFAULT_APP_NAME
    data_storage_path: str = ""


class BootstrapConfig:
    """应用引导配置（固定目录），用于存放应用名与数据存储位置。"""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or get_bootstrap_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()
        self._maybe_migrate_legacy()

    def _load(self) -> BootstrapData:
        if not self.path.exists():
            return BootstrapData()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return BootstrapData()
        return BootstrapData(
            app_name=str(raw.get("app_name") or DEFAULT_APP_NAME).strip()
            or DEFAULT_APP_NAME,
            data_storage_path=str(raw.get("data_storage_path") or "").strip(),
        )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(self._data), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _maybe_migrate_legacy(self) -> None:
        """若尚未配置存储位置，但旧默认目录已有数据库，则自动沿用。"""
        if self.is_storage_configured():
            return
        # 仅对真实引导配置文件做迁移，避免测试/自定义路径误命中本机旧数据
        if self.path.resolve() != get_bootstrap_path().resolve():
            return
        legacy_db = get_legacy_data_dir() / "tally.db"
        if legacy_db.exists():
            self._data.data_storage_path = str(legacy_db.parent.resolve())
            self._save()

    def reload(self) -> None:
        self._data = self._load()

    @property
    def app_name(self) -> str:
        return self._data.app_name or DEFAULT_APP_NAME

    def set_app_name(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("应用名称不能为空")
        self._data.app_name = name
        self._save()

    def is_storage_configured(self) -> bool:
        path = self._data.data_storage_path.strip()
        return bool(path)

    def get_data_storage_path(self) -> Optional[Path]:
        if not self.is_storage_configured():
            return None
        return Path(self._data.data_storage_path).expanduser().resolve()

    def get_db_path(self) -> Optional[Path]:
        storage = self.get_data_storage_path()
        if storage is None:
            return None
        return storage / "tally.db"

    def set_data_storage_path(self, path: str | Path) -> Path:
        if self.is_storage_configured():
            raise ValueError("数据存储位置已配置，不可修改")
        storage = Path(path).expanduser().resolve()
        if storage.exists() and not storage.is_dir():
            raise ValueError("数据存储位置必须是文件夹")
        storage.mkdir(parents=True, exist_ok=True)
        # 可写性检查
        probe = storage / ".tally_write_test"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            raise ValueError(f"数据存储位置不可写：{exc}") from exc
        self._data.data_storage_path = str(storage)
        self._save()
        return storage
