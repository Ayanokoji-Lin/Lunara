"""Lunara · 本地下载页

三件事：任务总览（下载中 / 已完成 / 失败）、逐条进度与操作、目录与批量控制。
演示态用 QTimer 推进进度；真实实现应接 QNetworkAccessManager / aria2，
断点续传状态落 SQLite，UI 这层完全不用改。
"""
from __future__ import annotations

import random

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ..core.player import Player
from ..data import DOWNLOADS, DownloadTask
from ..theme import THEME
from ..widgets.common import IconButton, font
from ..widgets.cover import CoverArt
from ..widgets.icons import pixmap
from ..widgets.progress import ThinProgress
from .base import BasePage

DOWNLOAD_DIR = r"D:\Music\Lunara"

STATE_TEXT = {"downloading": "下载中", "paused": "已暂停",
              "done": "已完成", "failed": "失败"}
STATE_STYLE = {
    "downloading": ("rgba(139, 92, 246, 0.16)", THEME["primary"],
                    "rgba(139, 92, 246, 0.30)"),
    "paused": ("rgba(148, 163, 184, 0.12)", THEME["text_sub"],
               "rgba(148, 163, 184, 0.22)"),
    "done": ("rgba(139, 92, 246, 0.10)", THEME["text_sub"],
             "rgba(139, 92, 246, 0.18)"),
    "failed": ("rgba(229, 72, 77, 0.14)", THEME["danger"],
               "rgba(229, 72, 77, 0.30)"),
}


class DownloadRow(QFrame):
    action = pyqtSignal(str, object)      # action, DownloadTask

    def __init__(self, task: DownloadTask, parent: QWidget | None = None):
        super().__init__(parent)
        self.task = task
        self.setObjectName("DownloadRow")

        h = QHBoxLayout(self)
        h.setContentsMargins(12, 10, 8, 10)
        h.setSpacing(14)

        self.cover = CoverArt(48, 6)
        self.cover.set_cover(task.track.seed, task.track.hue)
        h.addWidget(self.cover)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(7)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        self.title = QLabel(task.track.title)
        self.title.setFont(font(13, 500))
        self.title.setStyleSheet(f"color: {THEME['text_main']};")
        self.chip = QLabel()
        self.chip.setFixedHeight(19)
        top.addWidget(self.title)
        top.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch(1)

        self.btn_primary = IconButton("fa5s.pause", THEME["text_sub"], 12, 28, "暂停")
        self.btn_folder = IconButton("fa5s.folder-open", THEME["text_sub"], 12, 28,
                                     "打开所在文件夹")
        self.btn_delete = IconButton("fa5s.trash-alt", THEME["text_sub"], 12, 28,
                                     "删除任务")
        for b in (self.btn_primary, self.btn_folder, self.btn_delete):
            top.addWidget(b)
        col.addLayout(top)

        self.bar = ThinProgress(5)
        col.addWidget(self.bar)

        self.meta = QLabel()
        col.addWidget(self.meta)
        h.addLayout(col, 1)

        self.btn_primary.clicked.connect(self._on_primary)
        self.btn_folder.clicked.connect(lambda: self.action.emit("folder", self.task))
        self.btn_delete.clicked.connect(lambda: self.action.emit("delete", self.task))
        self.refresh()

    def _on_primary(self) -> None:
        if self.task.state == "failed":
            self.action.emit("retry", self.task)
        else:
            self.action.emit("toggle", self.task)

    def refresh(self) -> None:
        t = self.task
        self.bar.set_value(t.progress)
        self.bar.set_state(t.state)

        bg, fg, border = STATE_STYLE[t.state]
        self.chip.setText(STATE_TEXT[t.state])
        self.chip.setStyleSheet(
            f"QLabel {{ color: {fg}; background: {bg}; border: 1px solid {border};"
            f" border-radius: 9px; padding: 0 7px; font-size: 10px; }}")

        if t.state == "downloading":
            self.meta.setText(f"{t.speed:.1f} MB/s · {t.done_mb:.1f} / "
                              f"{t.size_mb:.1f} MB · {t.percent}%")
            self.meta.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 11px;")
        elif t.state == "paused":
            self.meta.setText(f"已暂停 · {t.done_mb:.1f} / {t.size_mb:.1f} MB")
            self.meta.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 11px;")
        elif t.state == "done":
            self.meta.setText(f"已完成 · {t.size_mb:.1f} MB · 已加入本地曲库")
            self.meta.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 11px;")
        else:
            self.meta.setText(f"下载失败 · {t.error}")
            self.meta.setStyleSheet(f"color: {THEME['danger']}; font-size: 11px;")

        self.btn_primary.setVisible(t.state != "done")
        if t.state == "downloading":
            self.btn_primary.set_icon_name("fa5s.pause")
            self.btn_primary.setToolTip("暂停")
        elif t.state == "paused":
            self.btn_primary.set_icon_name("fa5s.play")
            self.btn_primary.setToolTip("继续下载")
        elif t.state == "failed":
            self.btn_primary.set_icon_name("fa5s.redo")
            self.btn_primary.setToolTip("重试")
        self.btn_folder.setVisible(t.state == "done")


class DownloadPage(BasePage):
    FILTERS = ("全部", "下载中", "已完成", "失败")

    def __init__(self, player: Player, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.player = player
        self._tasks: list[DownloadTask] = list(DOWNLOADS)
        self._filter = 0
        self._rows: list[DownloadRow] = []

        # ---------- 页头 ----------
        head = QWidget()
        hv = QVBoxLayout(head)
        hv.setContentsMargins(0, 0, 0, 0)
        hv.setSpacing(6)
        title = QLabel("本地下载")
        title.setObjectName("PageTitle")
        self.sub = QLabel()
        self.sub.setObjectName("BodyText")
        hv.addWidget(title)
        hv.addWidget(self.sub)
        self.body.addWidget(head)

        # ---------- 工具条 ----------
        bar = QWidget()
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(8)
        self._tab_btns: list[QPushButton] = []
        for i, name in enumerate(self.FILTERS):
            b = QPushButton(name)
            b.setObjectName("ModeBtn")
            b.setCheckable(True)
            b.setFixedHeight(30)
            b.setMinimumWidth(68)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, idx=i: self.set_filter(idx))
            bh.addWidget(b)
            self._tab_btns.append(b)
        bh.addStretch(1)

        path_chip = QFrame()
        path_chip.setObjectName("PathChip")
        ph = QHBoxLayout(path_chip)
        ph.setContentsMargins(10, 0, 10, 0)
        ph.setSpacing(6)
        ico = QLabel()
        ico.setPixmap(pixmap("fa5s.folder", THEME["text_dim"], 11))
        ico.setFixedSize(12, 12)
        ph.addWidget(ico)
        ph.addWidget(QLabel(DOWNLOAD_DIR))
        path_chip.setFixedHeight(30)
        bh.addWidget(path_chip)

        self.btn_all = QPushButton("全部暂停")
        self.btn_all.setObjectName("GhostPill")
        self.btn_all.setFixedHeight(30)
        self.btn_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_all.clicked.connect(self._toggle_all)
        bh.addWidget(self.btn_all)
        self.body.addWidget(bar)

        # ---------- 列表 ----------
        self.panel = QFrame()
        self.panel.setObjectName("Panel")
        pv = QVBoxLayout(self.panel)
        pv.setContentsMargins(6, 6, 6, 8)
        pv.setSpacing(2)
        self._list = QVBoxLayout()
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(2)
        pv.addLayout(self._list)
        self.body.addWidget(self.panel)
        self.body.addStretch(1)

        # ---------- 演示用进度推进 ----------
        self._ticker = QTimer(self)
        self._ticker.setInterval(500)
        self._ticker.timeout.connect(self._tick)
        self._ticker.start()

        self.set_filter(0)

    # ---------------- 过滤 / 重建 ----------------
    def _filtered(self) -> list[DownloadTask]:
        if self._filter == 0:
            return list(self._tasks)
        if self._filter == 1:
            return [t for t in self._tasks if t.state in ("downloading", "paused")]
        if self._filter == 2:
            return [t for t in self._tasks if t.state == "done"]
        return [t for t in self._tasks if t.state == "failed"]

    def set_filter(self, index: int) -> None:
        self._filter = index
        for i, b in enumerate(self._tab_btns):
            b.setChecked(i == index)
        self._rebuild()

    def _rebuild(self) -> None:
        while self._list.count():
            item = self._list.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._rows.clear()

        tasks = self._filtered()
        if not tasks:
            empty = QLabel("这个分类下还没有任务")
            empty.setObjectName("BodyText")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setFixedHeight(140)
            self._list.addWidget(empty)
        else:
            for t in tasks:
                row = DownloadRow(t)
                row.action.connect(self._on_action)
                self._list.addWidget(row)
                self._rows.append(row)

        self._update_summary()

    def _update_summary(self) -> None:
        running = sum(1 for t in self._tasks if t.state == "downloading")
        paused = sum(1 for t in self._tasks if t.state == "paused")
        done = sum(1 for t in self._tasks if t.state == "done")
        failed = sum(1 for t in self._tasks if t.state == "failed")
        total = sum(t.size_mb for t in self._tasks)
        used = sum(t.size_mb * t.progress for t in self._tasks)
        bits = [f"{running} 个任务下载中"]
        if paused:
            bits.append(f"{paused} 个已暂停")
        bits.append(f"已完成 {done} 首")
        if failed:
            bits.append(f"{failed} 个失败")
        bits.append(f"占用 {used:.1f} / {total:.1f} MB")
        self.sub.setText(" · ".join(bits))
        self.btn_all.setText("全部暂停" if running else "全部开始")

    # ---------------- 操作 ----------------
    def _row_for(self, task: DownloadTask) -> DownloadRow | None:
        return next((r for r in self._rows if r.task is task), None)

    def _on_action(self, action: str, task: DownloadTask) -> None:
        if action == "toggle":
            task.state = "paused" if task.state == "downloading" else "downloading"
            self._refresh_task(task)
        elif action == "retry":
            task.state, task.progress = "downloading", 0.02
            task.error, task.speed = "", 2.0
            self._refresh_task(task)
        elif action == "delete":
            if task in self._tasks:
                self._tasks.remove(task)
            self._rebuild()
        elif action == "folder":
            QToolTip.showText(QCursor.pos(), f"已在资源管理器中打开 {DOWNLOAD_DIR}")

    def _refresh_task(self, task: DownloadTask) -> None:
        """状态变化后：仍在当前筛选里就只刷新那一行，否则重建列表。"""
        row = self._row_for(task)
        if row is not None and task in self._filtered():
            row.refresh()
            self._update_summary()
        else:
            self._rebuild()

    def _toggle_all(self) -> None:
        if any(t.state == "downloading" for t in self._tasks):
            for t in self._tasks:
                if t.state == "downloading":
                    t.state = "paused"
        else:
            for t in self._tasks:
                if t.state == "paused":
                    t.state = "downloading"
                    t.speed = random.uniform(1.6, 3.2)
        self._rebuild()

    # ---------------- 进度推进 ----------------
    def _tick(self) -> None:
        if not self.isVisible():      # 页面不在前台就不推进，省 CPU
            return
        finished = False
        for t in self._tasks:
            if t.state != "downloading":
                continue
            step = t.speed * 0.5 * 0.16 / max(0.1, t.size_mb)
            t.progress = min(1.0, t.progress + step)
            t.speed = max(0.4, t.speed + random.uniform(-0.15, 0.15))
            if t.progress >= 1.0:
                t.progress, t.state, t.speed = 1.0, "done", 0.0
                finished = True
        if finished:
            self._rebuild()
        else:
            for row in self._rows:
                row.refresh()
            self._update_summary()
