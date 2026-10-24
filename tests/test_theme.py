"""主题切换：令牌原地替换、颜色取值、两套主题都完整。"""
from __future__ import annotations

import pytest

from lunara import theme


@pytest.fixture(autouse=True)
def restore_dark():
    yield
    theme.apply("dark")


def test_default_is_dark() -> None:
    theme.apply("dark")
    assert theme.THEME["bg_main"] == theme.DARK["bg_main"]


def test_apply_light_changes_tokens() -> None:
    theme.apply("light")

    assert theme.THEME["bg_main"] == theme.LIGHT["bg_main"]
    assert theme.THEME["text_main"] == theme.LIGHT["text_main"]


def test_apply_is_in_place() -> None:
    """各模块 `from ..theme import THEME` 拿的是同一个 dict，必须原地更新。"""
    before = id(theme.THEME)
    theme.apply("light")
    assert id(theme.THEME) == before


def test_unknown_theme_falls_back_to_dark() -> None:
    theme.apply("no-such-theme")
    assert theme.THEME["bg_main"] == theme.DARK["bg_main"]


def test_qcolor_uses_token_and_alpha() -> None:
    theme.apply("dark")
    color = theme.qcolor("bg_main", 128)

    assert color.alpha() == 128
    assert color.name() == theme.DARK["bg_main"].lower()


def test_both_themes_define_same_keys() -> None:
    assert set(theme.DARK) == set(theme.LIGHT)
