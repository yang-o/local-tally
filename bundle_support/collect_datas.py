"""供 PyInstaller .spec 收集运行时资源。"""

from __future__ import annotations

from pathlib import Path


def collect_datas() -> list[tuple[str, str]]:
    datas: list[tuple[str, str]] = []

    try:
        import customtkinter

        ctk_root = Path(customtkinter.__file__).resolve().parent
        assets = ctk_root / "assets"
        if assets.exists():
            datas.append((str(assets), "customtkinter/assets"))
    except Exception:
        pass

    return datas
