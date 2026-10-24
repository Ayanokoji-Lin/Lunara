"""应用数据目录的唯一出口。

所有要落盘的东西（登录态、封面缓存、下载任务、设置）都从这里取路径，
避免各模块各写一份 ``%APPDATA%`` 判断。
"""
from __future__ import annotations

import os
from pathlib import Path

#: 应用数据根目录（Windows 是 %APPDATA%\Lunara，其它平台退回 ~/Lunara）
APP_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "Lunara"

#: 登录态（DPAPI 加密）
SESSION_FILE = APP_DIR / "session.enc"
#: 设置
SETTINGS_FILE = APP_DIR / "settings.json"
#: 下载任务表
TASKS_DB = APP_DIR / "tasks.db"
#: 封面磁盘缓存
COVERS_DIR = APP_DIR / "covers"


def ensure_app_dir() -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DIR


def default_download_dir() -> Path:
    """默认下载目录：有 D 盘就沿用 D:\\Music\\Lunara，否则落到用户音乐目录。"""
    if os.name == "nt" and Path("D:/").exists():
        return Path("D:/Music/Lunara")
    return Path.home() / "Music" / "Lunara"
