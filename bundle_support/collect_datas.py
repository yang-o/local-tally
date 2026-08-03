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


def collect_package_resources() -> tuple[list, list, list[str]]:
    """收集 customtkinter / tkcalendar / babel 的数据、二进制与隐藏导入。"""
    datas = collect_datas()
    binaries: list = []
    hiddenimports = [
        "PIL._tkinter_finder",
        "babel.numbers",
        "tkcalendar",
        "customtkinter",
    ]

    try:
        from PyInstaller.utils.hooks import collect_all
    except Exception:
        return datas, binaries, hiddenimports

    for pkg in ("customtkinter", "tkcalendar", "babel"):
        try:
            pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
            datas += pkg_datas
            binaries += pkg_binaries
            hiddenimports += pkg_hidden
        except Exception:
            continue

    # 去重并保持顺序
    hiddenimports = list(dict.fromkeys(hiddenimports))
    return datas, binaries, hiddenimports
