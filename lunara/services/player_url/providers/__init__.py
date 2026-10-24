"""音源 Provider 出口。"""
from __future__ import annotations

from .gdstudio import GdStudioAdapter
from .official import OfficialProvider

__all__ = ["GdStudioAdapter", "OfficialProvider"]
