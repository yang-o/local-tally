#!/usr/bin/env python3
"""本机构建当前平台的桌面应用。

用法:
  python scripts/build.py          # 自动识别当前系统
  python scripts/build.py mac      # 仅 macOS
  python scripts/build.py win      # 仅 Windows

说明:
  PyInstaller 不支持交叉编译。macOS 只能打 .app，Windows 只能打 .exe。
  若要一次产出双端产物，请推送到 GitHub 触发 .github/workflows/build.yml。
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def build_mac() -> Path:
    if sys.platform != "darwin":
        raise SystemExit("macOS 打包只能在 macOS 上执行")
    _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(ROOT / "build_macos.spec"),
        ]
    )
    app_path = ROOT / "dist" / "Tally.app"
    if not app_path.exists():
        raise SystemExit("未找到 dist/Tally.app，打包可能失败")
    print(f"macOS 应用已生成: {app_path}")
    return app_path


def build_win() -> Path:
    if sys.platform != "win32":
        raise SystemExit("Windows 打包只能在 Windows 上执行")
    _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(ROOT / "build_windows.spec"),
        ]
    )
    exe_dir = ROOT / "dist" / "Tally"
    exe_path = exe_dir / "Tally.exe"
    if not exe_path.exists():
        raise SystemExit("未找到 dist/Tally/Tally.exe，打包可能失败")
    print(f"Windows 应用已生成: {exe_path}")
    return exe_path


def main() -> None:
    parser = argparse.ArgumentParser(description="打包 Tally 桌面应用")
    parser.add_argument(
        "target",
        nargs="?",
        choices=["auto", "mac", "win"],
        default="auto",
        help="打包目标（默认按当前系统）",
    )
    args = parser.parse_args()

    target = args.target
    if target == "auto":
        system = platform.system().lower()
        if system == "darwin":
            target = "mac"
        elif system == "windows":
            target = "win"
        else:
            raise SystemExit(f"当前系统 {platform.system()} 暂不支持桌面打包")

    # 确保依赖可用
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("正在安装打包依赖...")
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(ROOT / "requirements-build.txt"),
            ]
        )

    dist = ROOT / "dist"
    build = ROOT / "build"
    if dist.exists():
        shutil.rmtree(dist)
    if build.exists():
        shutil.rmtree(build)

    if target == "mac":
        build_mac()
    else:
        build_win()


if __name__ == "__main__":
    main()
