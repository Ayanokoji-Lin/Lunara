"""Lunara · 设计令牌（Design Tokens）与全局 QSS 生成器

设计基调：深空、星轨、月光。
所有颜色统一收敛到 THEME 字典，QSS 通过 string.Template 注入，
换肤时只需要替换字典 + 重新 setStyleSheet，不需要改动任何业务代码。
"""
from __future__ import annotations

from string import Template

# --------------------------------------------------------------------------
# 1. 调色板
# --------------------------------------------------------------------------
DARK = {
    # 品牌
    "primary": "#8B5CF6",          # 星夜紫
    "primary_hover": "#9F7AFA",
    "primary_press": "#7C3AED",
    "primary_soft": "rgba(139, 92, 246, 0.16)",
    "primary_ghost": "rgba(139, 92, 246, 0.10)",
    "accent": "#E2E8F0",           # 月光银
    # 背景层级
    "bg_main": "#0F172A",          # 深空黑
    "bg_panel": "#1E293B",         # 侧栏 / 顶栏 / 播放栏 / 卡片
    "bg_elev": "#334155",          # 卡片悬停
    "bg_input": "rgba(15, 23, 42, 0.62)",
    "bg_hover": "rgba(255, 255, 255, 0.06)",
    "bg_active": "rgba(51, 65, 85, 0.60)",
    "bg_overlay": "rgba(15, 23, 42, 0.72)",
    # 文字
    "text_main": "#F8FAFC",        # 月光白
    "text_sub": "#94A3B8",         # 星尘灰
    "text_dim": "#64748B",         # 歌词未播放态
    # 线条
    "border": "#334155",
    "border_soft": "rgba(255, 255, 255, 0.07)",
    "danger": "#E5484D",
    # 形状
    "radius": "6px",
    "radius_md": "8px",
    "radius_lg": "12px",
    "radius_win": "14px",
}

# 亮色模式（月光白）—— 预留扩展，切换时只需 theme.apply(LIGHT)
LIGHT = {
    **DARK,
    "primary": "#7C3AED",
    "primary_hover": "#8B5CF6",
    "primary_press": "#6D28D9",
    "primary_soft": "rgba(124, 58, 237, 0.12)",
    "primary_ghost": "rgba(124, 58, 237, 0.08)",
    "accent": "#0F172A",
    "bg_main": "#F8FAFC",
    "bg_panel": "#FFFFFF",
    "bg_elev": "#F1F5F9",
    "bg_input": "rgba(241, 245, 249, 0.90)",
    "bg_hover": "rgba(15, 23, 42, 0.05)",
    "bg_active": "rgba(15, 23, 42, 0.06)",
    "bg_overlay": "rgba(248, 250, 252, 0.72)",
    "text_main": "#0F172A",
    "text_sub": "#64748B",
    "text_dim": "#94A3B8",
    "border": "#E2E8F0",
    "border_soft": "rgba(15, 23, 42, 0.08)",
}

# 当前生效的主题（运行时被 theme.py:apply() 修改）
THEME = dict(DARK)

# --------------------------------------------------------------------------
# 2. 尺度令牌
# --------------------------------------------------------------------------
METRICS = {
    "win_min_w": 1056,
    "win_min_h": 752,
    "content_max_w": 1490,
    "sidebar_w": 204,
    "topbar_h": 56,
    "player_h": 80,
    "page_pad": 40,
    "gap": 24,
}

FONT_UI = '"Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "SF Pro Display"'

# --------------------------------------------------------------------------
# 3. 全局样式表
# --------------------------------------------------------------------------
_QSS = Template(
    """
/* ===================== 基础 ===================== */
* { outline: 0; }
QWidget {
    color: $text_main;
    font-family: $font_ui;
}
QMainWindow, QDialog { background: transparent; }

QToolTip {
    background-color: $bg_panel;
    color: $text_main;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
}

/* ===================== 窗口骨架 ===================== */
QWidget#WindowRoot {
    background-color: $bg_main;
    border: 1px solid $border_soft;
    border-radius: $radius_win;
}
QWidget#WindowRoot[windowState="maximized"] {
    border-radius: 0px;
    border: none;
}
QWidget#ContentArea { background-color: $bg_main; }
QStackedWidget { background: transparent; }

/* ===================== 侧边栏 ===================== */
QFrame#Sidebar {
    background-color: $bg_panel;
    border: none;
    border-right: 1px solid $border_soft;
    border-top-left-radius: $radius_win;
    border-bottom-left-radius: $radius_win;
}
QLabel#SidebarSection {
    color: $text_dim;
    font-size: 12px;
    padding: 0 0 0 14px;
}
QPushButton#SidebarItem {
    background: transparent;
    border: none;
    border-radius: $radius;
    color: $text_sub;
    text-align: left;
    padding-left: 38px;
    padding-right: 10px;
    min-height: 38px;
    font-size: 14px;
}
QPushButton#SidebarItem:hover {
    background-color: $bg_hover;
    color: $text_main;
}
QPushButton#SidebarItem:checked {
    background-color: $bg_active;
    color: $text_main;
}
QPushButton#SidebarItem:checked:hover { background-color: rgba(51, 65, 85, 0.78); }
QPushButton#SidebarItem[indicator="true"] {
    background-color: $primary_soft;
    color: $text_main;
    font-weight: 600;
}
QPushButton#SidebarSubItem {
    background: transparent;
    border: none;
    color: $text_dim;
    text-align: left;
    padding-left: 38px;
    min-height: 30px;
    font-size: 13px;
}
QPushButton#SidebarSubItem:hover { color: $text_main; }
QPushButton#SidebarSubItem:checked { color: $primary; }
QPushButton#SidebarGroup {
    background: transparent;
    border: none;
    color: $text_dim;
    text-align: left;
    padding-left: 14px;
    min-height: 28px;
    font-size: 11px;
}
QPushButton#SidebarGroup:hover { color: $text_sub; }
QFrame#NavIndicator {
    background-color: $primary;
    border-radius: 1px;
}

/* ===================== 顶栏 ===================== */
QFrame#TopBar {
    background-color: $bg_panel;
    border: none;
    border-bottom: 1px solid $border_soft;
    border-top-right-radius: $radius_win;
}
QLineEdit#SearchInput {
    background-color: $bg_input;
    border: 1px solid $border_soft;
    border-radius: 16px;
    padding-left: 34px;
    padding-right: 34px;
    min-height: 32px;
    color: $text_main;
    font-size: 12px;
    selection-background-color: $primary;
}
QLineEdit#SearchInput:hover { background-color: rgba(15, 23, 42, 0.80); }
QLineEdit#SearchInput:focus {
    border: 1px solid rgba(139, 92, 246, 0.55);
    background-color: rgba(15, 23, 42, 0.88);
}
QPushButton#IconBtn {
    background: transparent;
    border: none;
    border-radius: 6px;
}
QPushButton#IconBtn:hover { background-color: $bg_hover; }
QPushButton#IconBtn:pressed { background-color: rgba(255, 255, 255, 0.12); }
QPushButton#CloseBtn {
    background: transparent;
    border: none;
    border-top-right-radius: $radius_win;
}
QPushButton#CloseBtn:hover { background-color: $danger; }
QLabel#Avatar { border-radius: 14px; }
QToolButton#AvatarButton { border: none; background: transparent; border-radius: 15px; }
QFrame#TopBarDivider { background-color: $border_soft; }

/* ===================== 内容区 / 页头 ===================== */
QScrollArea#PageScroll { background: transparent; border: none; }
QScrollArea#PageScroll > QWidget { background: transparent; }
QScrollArea#PageScroll > QWidget > QWidget { background: transparent; }
QWidget#PageCanvas { background: transparent; }
QLabel#PageTitle {
    font-size: 22px;
    font-weight: 600;
    color: $text_main;
}
QLabel#SectionTitle {
    font-size: 17px;
    font-weight: 600;
    color: $text_main;
}
QLabel#SectionHint { color: $text_dim; font-size: 11px; }
QLabel#BodyText { color: $text_sub; font-size: 12px; }
QLabel#MetaText { color: $text_dim; font-size: 11px; }
QLabel#TrackTitle {
    font-size: 24px;
    font-weight: 600;
    color: $text_main;
}
QPushButton#LinkBtn {
    background: transparent;
    border: none;
    color: $text_dim;
    font-size: 11px;
    padding: 2px 4px;
}
QPushButton#LinkBtn:hover { color: $primary; }

/* ===================== 按钮 ===================== */
QPushButton#PrimaryPill {
    background-color: $primary;
    color: #FFFFFF;
    border: none;
    border-radius: 17px;
    padding: 0 22px;
    min-height: 36px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#PrimaryPill:hover { background-color: $primary_hover; }
QPushButton#PrimaryPill:pressed { background-color: $primary_press; }
QPushButton#SmallPill {
    background-color: $bg_hover;
    color: $text_sub;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 0 12px;
    min-height: 26px;
    max-height: 26px;
    font-size: 11px;
}
QPushButton#SmallPill:hover {
    background-color: rgba(255, 255, 255, 0.10);
    color: $text_main;
    border: 1px solid $bg_elev;
}

QPushButton#GhostPill {
    background-color: $bg_hover;
    color: $text_main;
    border: 1px solid $border;
    border-radius: 16px;
    padding: 0 18px;
    min-height: 34px;
    font-size: 12px;
}
QPushButton#GhostPill:hover {
    background-color: rgba(255, 255, 255, 0.12);
    border: 1px solid $bg_elev;
}
QPushButton#GhostPill:checked {
    color: $primary;
    border: 1px solid rgba(139, 92, 246, 0.55);
    background-color: $primary_ghost;
}
QPushButton#PlayFab {
    background-color: $primary;
    border: none;
    border-radius: 18px;
}
QPushButton#PlayFab:hover { background-color: $primary_hover; }
QPushButton#PlayFab:pressed { background-color: $primary_press; }
QPushButton#CircleIconBtn {
    background-color: rgba(255, 255, 255, 0.06);
    border: none;
    border-radius: 15px;
}
QPushButton#CircleIconBtn:hover { background-color: rgba(255, 255, 255, 0.14); }
QPushButton#ModeBtn {
    background: transparent;
    border: none;
    border-radius: 6px;
    color: $text_sub;
    padding: 4px 10px;
    font-size: 11px;
}
QPushButton#ModeBtn:hover { color: $text_main; background-color: $bg_hover; }
QPushButton#ModeBtn:checked {
    color: $primary;
    background-color: $primary_ghost;
}

/* ===================== 卡片 ===================== */
QFrame#Card {
    background-color: $bg_panel;
    border: 1px solid $border_soft;
    border-radius: $radius_md;
}
QFrame#Card:hover {
    background-color: $bg_elev;
    border: 1px solid $bg_elev;
}
QFrame#Panel {
    background-color: $bg_panel;
    border: 1px solid $border_soft;
    border-radius: $radius_lg;
}
QFrame#Divider { background-color: $border_soft; max-height: 1px; min-height: 1px; }
QFrame#DownloadRow {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
}
QFrame#DownloadRow:hover {
    background-color: rgba(51, 65, 85, 0.45);
    border: 1px solid $border_soft;
}
QFrame#PathChip {
    background-color: $bg_hover;
    border: 1px solid $border_soft;
    border-radius: 8px;
}
QFrame#PathChip QLabel { color: $text_dim; font-size: 11px; }

/* ===================== 滚动条（极限美化） ===================== */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px 0px 2px 0px;
    border: none;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.30); }
QScrollBar::handle:vertical:pressed { background: rgba(139, 92, 246, 0.65); }
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0px 2px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: rgba(255, 255, 255, 0.30); }
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0px;
    height: 0px;
    background: transparent;
    border: none;
}
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QScrollBar::up-arrow, QScrollBar::down-arrow,
QScrollBar::left-arrow, QScrollBar::right-arrow {
    width: 0px;
    height: 0px;
    background: transparent;
}
QAbstractScrollArea::corner { background: transparent; }

/* ===================== 播放栏 ===================== */
QFrame#PlayerBar {
    background-color: $bg_panel;
    border: none;
    border-top: 1px solid $border;
    border-bottom-left-radius: $radius_win;
    border-bottom-right-radius: $radius_win;
}
QLabel#PlayerTitle { color: $text_main; font-size: 13px; font-weight: 600; }
QLabel#PlayerArtist { color: $text_sub; font-size: 11px; }
QLabel#TimeLabel { color: $text_dim; font-size: 10px; }
QLabel#CoverMini { border-radius: 4px; }

/* ===================== 滑块 ===================== */
QSlider#SeekSlider { min-height: 16px; background: transparent; }
QSlider#SeekSlider::groove:horizontal {
    height: 4px;
    background: $border;
    border-radius: 2px;
}
QSlider#SeekSlider::sub-page:horizontal {
    background: $primary;
    border-radius: 2px;
}
QSlider#SeekSlider::add-page:horizontal { background: $border; border-radius: 2px; }
QSlider#SeekSlider::handle:horizontal {
    width: 11px;
    height: 11px;
    margin: -4px 0px;
    border-radius: 5px;
    background: #FFFFFF;
}
QSlider#SeekSlider::handle:horizontal:hover {
    width: 14px;
    height: 14px;
    margin: -5px 0px;
    border-radius: 6px;
    background: #FFFFFF;
}
QSlider#VolumeSlider { min-height: 14px; background: transparent; }
QSlider#VolumeSlider::groove:horizontal {
    height: 3px;
    background: $border;
    border-radius: 2px;
}
QSlider#VolumeSlider::sub-page:horizontal {
    background: $primary;
    border-radius: 2px;
}
QSlider#VolumeSlider::handle:horizontal {
    width: 9px;
    height: 9px;
    margin: -3px 0px;
    border-radius: 4px;
    background: #FFFFFF;
}
QSlider#VolumeSlider::handle:horizontal:hover { background: $primary; }

/* ===================== 表格（歌曲列表） ===================== */
QTableView#TrackTable {
    background: transparent;
    border: none;
    gridline-color: transparent;
    selection-background-color: transparent;
    selection-color: $text_main;
    alternate-background-color: transparent;
}
QTableView#TrackTable::item {
    border: none;
    padding: 0px;
}
QTableView#TrackTable QHeaderView { background: transparent; border: none; }
QHeaderView { background: transparent; }
QHeaderView::section { background: transparent; border: none; }
QTableView#TrackTable QHeaderView::section {
    background: transparent;
    color: $text_dim;
    border: none;
    border-bottom: 1px solid $border_soft;
    padding: 6px 8px;
    font-size: 11px;
}
QTableView#TrackTable QHeaderView::section:hover { color: $text_sub; }
QTableCornerButton::section { background: transparent; border: none; }

/* ===================== 菜单 ===================== */
QMenu {
    background-color: $bg_elev;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 26px 7px 14px;
    border-radius: 6px;
    color: $text_sub;
    font-size: 12px;
}
QMenu::item:selected { background-color: $primary_soft; color: $text_main; }
QMenu::separator { height: 1px; background: $border_soft; margin: 6px 8px; }

/* ===================== 设置页 ===================== */
QPushButton#SettingsNav {
    background: transparent;
    border: none;
    border-radius: $radius;
    color: $text_sub;
    text-align: left;
    padding-left: 16px;
    min-height: 34px;
    font-size: 13px;
}
QPushButton#SettingsNav:hover { background-color: $bg_hover; color: $text_main; }
QPushButton#SettingsNav:checked {
    background-color: $primary_soft;
    color: $primary;
    font-weight: 600;
}
/* QCheckBox 胶囊开关（备用方案；默认使用自绘 Switch 以获得滑块动画） */
QCheckBox#PillCheck::indicator {
    width: 36px;
    height: 20px;
    border-radius: 10px;
    background-color: $bg_elev;
    border: 1px solid $border;
}
QCheckBox#PillCheck::indicator:checked {
    background-color: $primary;
    border: 1px solid $primary;
}
QComboBox {
    background-color: $bg_input;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 24px;
    color: $text_main;
}
QComboBox:hover { border: 1px solid $primary; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid $text_dim;
    width: 0; height: 0;
    margin-right: 8px;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: $bg_elev;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 6px;
    selection-background-color: $primary_soft;
    selection-color: $text_main;
    outline: none;
}
QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding-left: 10px;
    border-radius: 6px;
    color: $text_main;
}
QComboBox QAbstractItemView::item:hover {
    background-color: $primary_soft;
}

QPushButton#QualityChip {
    background-color: rgba(139, 92, 246, 0.16);
    color: $primary;
    border: 1px solid rgba(139, 92, 246, 0.45);
    border-radius: 12px;
    padding: 0 10px;
    font-size: 11px;
}
QPushButton#QualityChip:hover {
    background-color: rgba(139, 92, 246, 0.28);
    border: 1px solid rgba(139, 92, 246, 0.7);
}

/* ===================== 播放列表 ===================== */
QFrame#QueuePanel {
    background-color: $bg_panel;
    border: 1px solid $border;
    border-radius: 14px;
}
QWidget#QueueHead {
    background: transparent;
    border-bottom: 1px solid $border_soft;
}
QPushButton#QueueAction {
    background: transparent;
    border: none;
    color: $text_sub;
    font-size: 11px;
    padding: 4px 6px;
    border-radius: 6px;
}
QPushButton#QueueAction:hover {
    background-color: $bg_hover;
    color: $text_main;
}
QPushButton#QueueRemove {
    background: transparent;
    border: none;
    border-radius: 11px;
}
QPushButton#QueueRemove:hover { background-color: $bg_hover; }

/* ===================== 提示框 ===================== */
QDialog#LunaraDialog {
    background-color: $bg_elev;
    border: 1px solid $border;
    border-radius: 14px;
}
QLabel#DialogTitle {
    color: $text_main;
    font-size: 14px;
    font-weight: 600;
}
QLabel#DialogBody {
    color: $text_sub;
    font-size: 12px;
    line-height: 20px;
}

/* ===================== 歌词 ===================== */
QLabel#LyricLine {
    color: $text_dim;
    font-size: 14px;
}
QLabel#LyricLine[active="true"] {
    color: $text_main;
    font-size: 19px;
    font-weight: 600;
}
QWidget#LyricViewport { background: transparent; }
QWidget#NowPlayingRoot { background: transparent; }
"""
)


def build_qss(theme: dict | None = None) -> str:
    """把令牌注入 QSS 模板。$font_ui 之外没有其它 $ 符号，Template 是安全的。"""
    t = dict(theme or THEME)
    t.setdefault("font_ui", FONT_UI)
    return _QSS.substitute(t)


def qss(theme: dict | None = None) -> str:
    return build_qss(theme)


# --------------------------------------------------------------------------
# 3. 运行时切换
# --------------------------------------------------------------------------
THEMES = {"dark": DARK, "light": LIGHT}
DEFAULT_THEME = "dark"


def apply(name: str = DEFAULT_THEME) -> dict:
    """切换当前主题。

    ``THEME`` 是同一个 dict 对象（各模块 ``from ..theme import THEME``），
    所以原地清空再更新，所有引用方都会看到新值。**只影响之后创建的控件**，
    切换后需要重建窗口（实际做法是重启应用）。
    """
    target = THEMES.get(name, DARK)
    THEME.clear()
    THEME.update(target)
    return THEME


def qcolor(token: str, alpha: int = 255):
    """按令牌取颜色，可指定 alpha（QPainter 用）。"""
    from PyQt6.QtGui import QColor

    color = QColor(THEME.get(token, "#000000"))
    color.setAlpha(alpha)
    return color
