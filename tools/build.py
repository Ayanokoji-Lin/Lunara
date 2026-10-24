"""打包：PyInstaller onedir（`dist/Lunara/Lunara.exe`）。

    .venv/Scripts/python.exe tools/build.py

注意：
- 用 onedir 而不是 onefile——onefile 每次启动都要解压 200MB+，体验很差。
- 需要 QtWebEngine 的资源（登录窗口），PyInstaller 的 PyQt6 hook 会自动带上，
  所以体积较大属于正常。
- 产物不提交仓库（`.gitignore` 已忽略 build/ 与 dist/）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "Lunara"

ARGS = [
    "--noconfirm",
    "--clean",
    "--windowed",                     # 不弹控制台
    "--name", "Lunara",
    "--collect-data", "qtawesome",    # 图标字体
    "--hidden-import", "PyQt6.QtWebEngineWidgets",
    "--hidden-import", "PyQt6.QtWebEngineCore",
    "--exclude-module", "pytest",
    "--exclude-module", "tests",
    "--exclude-module", "tools",
    str(ROOT / "main.py"),
]


def main() -> int:
    print("打包中（首次约 3–8 分钟，产物 200MB+）…")
    result = subprocess.run([sys.executable, "-m", "PyInstaller", *ARGS], cwd=ROOT)
    if result.returncode != 0:
        print("!! 打包失败，看上面的输出")
        return result.returncode

    exe = DIST / "Lunara.exe"
    if exe.exists():
        size = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file()) / 1e6
        print(f"完成：{exe}（整个目录 {size:.0f} MB）")
        return 0
    print("!! 没有找到 dist/Lunara/Lunara.exe")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
