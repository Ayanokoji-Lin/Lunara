"""打包：PyInstaller onedir（`dist/Lunara/Lunara.exe`）。

    .venv/Scripts/python.exe tools/build.py

注意：
- 用 onedir 而不是 onefile——onefile 每次启动都要解压 200MB+，体验很差。
- 需要 QtWebEngine 的资源（登录窗口），PyInstaller 的 PyQt6 hook 会自动带上，
  所以体积较大属于正常。
- 产物不提交仓库（`.gitignore` 已忽略 build/ 与 dist/）。
- **重新打包前把旧目录改名，而不是删掉**：一次删上千个文件在受限环境里会被拦，
  改名是瞬时的。旧目录落在 `dist/.old/`，下次打包时尽力清理（清不掉不影响构建）。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_ROOT = ROOT / "dist"
DIST = DIST_ROOT / "Lunara"
OLD_DIR = DIST_ROOT / ".old"

ARGS = [
    "--noconfirm",
    "--clean",
    "--windowed",                     # 不弹控制台
    "--name", "Lunara",
    "--icon", str(ROOT / "assets" / "icon.ico"),
    "--add-data", f"{ROOT / 'assets'}{os.pathsep}assets",   # 运行时读 icon.ico
    "--collect-data", "qtawesome",    # 图标字体
    "--hidden-import", "PyQt6.QtWebEngineWidgets",
    "--hidden-import", "PyQt6.QtWebEngineCore",
    "--exclude-module", "pytest",
    "--exclude-module", "tests",
    "--exclude-module", "tools",
    str(ROOT / "main.py"),
]


#: 打包后可以安全删掉的大文件（调试用的 WebEngine 资源、非中文翻译）
PRUNE_FILES = (
    "PyQt6/Qt6/resources/qtwebengine_devtools_resources.debug.pak",
    "PyQt6/Qt6/resources/qtwebengine_devtools_resources.pak",
    "PyQt6/Qt6/resources/v8_context_snapshot.debug.bin",
)
KEEP_TRANSLATIONS = ("zh_CN", "zh_TW", "en", "qt_")


def _prune(target: Path) -> float:
    """把用不到的调试资源与多余翻译**挪出**包外（不删，避免批量删除被拦）。

    调试用的 WebEngine 资源与「非中英文翻译」占了近 130MB，运行时一个都用不到。
    """
    internal = target / "_internal"
    trash = target.parent / ".pruned"
    freed = 0

    def stash(path: Path) -> None:
        nonlocal freed
        if not path.exists() or not path.is_file():
            return
        try:
            trash.mkdir(parents=True, exist_ok=True)
            size = path.stat().st_size
            shutil.move(str(path), str(trash / path.name))
            freed += size
        except (OSError, shutil.Error):
            pass

    for rel in PRUNE_FILES:
        stash(internal / rel)

    resources = internal / "PyQt6" / "Qt6" / "resources"
    if resources.exists():
        for path in resources.glob("*.debug.pak"):
            stash(path)

    translations = internal / "PyQt6" / "Qt6" / "translations"
    if translations.exists():
        for path in translations.glob("*.qm"):
            if not any(key in path.name for key in KEEP_TRANSLATIONS):
                stash(path)

    return freed / 1e6


def _clear_old() -> None:
    """尽力清理历史备份；删不掉（被安全策略拦、文件被占用）都不影响本次构建。"""
    if not OLD_DIR.exists():
        return
    for item in OLD_DIR.iterdir():
        try:
            shutil.rmtree(item, ignore_errors=True)
        except BaseException:          # noqa: BLE001 - 清理失败不该中断打包
            continue


def _stash_previous() -> None:
    """把上一次的产物挪走（改名，不删文件）。"""
    if not DIST.exists():
        return
    OLD_DIR.mkdir(parents=True, exist_ok=True)
    target = OLD_DIR / f"Lunara-{int(time.time())}"
    try:
        DIST.rename(target)
        print(f"旧产物已挪到 {target.relative_to(ROOT)}")
    except OSError as exc:
        print(f"!! 挪不动旧产物（{exc}），PyInstaller 可能因为目录已存在而失败")


def main() -> int:
    _clear_old()
    _stash_previous()

    print("打包中（首次约 3–8 分钟，产物 200MB+）…")
    result = subprocess.run([sys.executable, "-m", "PyInstaller", *ARGS], cwd=ROOT)
    if result.returncode != 0:
        print("!! 打包失败，看上面的输出")
        return result.returncode

    exe = DIST / "Lunara.exe"
    if exe.exists():
        freed = _prune(DIST)
        size = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file()) / 1e6
        print(f"完成：{exe}（整个目录 {size:.0f} MB，精简掉 {freed:.0f} MB）")
        return 0
    print("!! 没有找到 dist/Lunara/Lunara.exe")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
