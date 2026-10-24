"""UI 测试共用的 QApplication。

必须**全局唯一**：每个测试文件各建一个 ``QApplication`` 的话，前一个被回收后
后面的控件就没有有效的应用实例，``show()`` 不生效、布局高度全是 0，
表现为「滚动位置怎么算都是 0」这种莫名其妙的失败。
"""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtWidgets", reason="需要 PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qt_app():
    instance = QApplication.instance() or QApplication([])
    yield instance
