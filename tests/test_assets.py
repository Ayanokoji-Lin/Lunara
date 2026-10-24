"""图标资源：文件存在、尺寸齐全。

图标是打包时嵌进 exe 的，丢了不会报错、只会变成默认图标——所以拿测试盯一下。
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
EXPECTED = {16, 24, 32, 48, 64, 128, 256}


def test_icon_files_exist() -> None:
    for name in ("icon.ico", "icon.png"):
        path = ASSETS / name
        assert path.exists(), f"缺少 {name}"
        assert path.stat().st_size > 1024, f"{name} 太小，可能是空文件"


def test_ico_contains_all_sizes() -> None:
    pytest.importorskip("PIL", reason="Pillow 只在开发环境用")
    from PIL import Image

    with Image.open(ASSETS / "icon.ico") as ico:
        sizes = {width for width, _ in ico.ico.sizes()}

    assert EXPECTED <= sizes, f"ICO 缺少尺寸：{EXPECTED - sizes}"


def test_png_is_1024() -> None:
    pytest.importorskip("PIL", reason="Pillow 只在开发环境用")
    from PIL import Image

    with Image.open(ASSETS / "icon.png") as png:
        assert png.size == (1024, 1024)
