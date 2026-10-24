"""Lunara · 本地下载页

数据来源是 ``services.download.DownloadService``：页面不再自己推进进度，
只做三件事——把任务画出来、把点击转成服务调用、把服务事件转成界面变化。

状态：queued（排队）/ downloading / paused / done / failed。
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QLineEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.player import Player
from ..widgets.common import RoundedCombo, style_combo
from ..widgets.dialog import confirm
from ..widgets.anim import Coalescer
from ..core.player import Player
from ..widgets.dialog import confirm
from ..data import DownloadTask, Track
from ..services.download.naming import format_size
from ..services.download.notice import NOTICE_TEXT, write_notice_file
from ..services.download.service import DownloadEvent, DownloadService
from ..services.settings_store import SettingsStore
from ..theme import THEME
from ..widgets.common import IconButton, font
from ..widgets.cover import CoverArt
from ..widgets.icons import pixmap
from ..widgets.notice import InlineBanner
from ..widgets.progress import ThinProgress
from .base import BasePage

STATE_TEXT = {"queued": "排队中", "downloading": "下载中", "paused": "已暂停",
              "done": "已完成", "failed": "失败"}
STATE_STYLE = {
    "downloading": ("rgba(139, 92, 246, 0.16)", THEME["primary"],
                    "rgba(139, 92, 246, 0.30)"),
    "queued": ("rgba(148, 163, 184, 0.12)", THEME["text_sub"],
               "rgba(148, 163, 184, 0.22)"),
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
        self.cover.set_cover(task.track.seed, task.track.hue, task.track.cover_url)
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

        self.btn_play = IconButton("fa5s.play", THEME["text_sub"], 12, 28, "播放本地文件")
        self.btn_play = IconButton("fa5s.play", THEME["text_sub"], 12, 28, "播放本地文件")
        self.btn_primary = IconButton("fa5s.pause", THEME["text_sub"], 12, 28, "暂停")
        self.btn_folder = IconButton("fa5s.folder-open", THEME["text_sub"], 12, 28,
                                     "打开所在文件夹")
        self.btn_delete = IconButton("fa5s.trash-alt", THEME["text_sub"], 12, 28,
                                     "删除任务（不删除已下载文件）")
        for b in (self.btn_play, self.btn_primary, self.btn_folder, self.btn_delete):
            top.addWidget(b)
        col.addLayout(top)

        self.bar = ThinProgress(5)
        col.addWidget(self.bar)

        self.meta = QLabel()
        col.addWidget(self.meta)
        h.addLayout(col, 1)

        self.btn_play.clicked.connect(lambda: self.action.emit("play", self.task))
        self.btn_play.clicked.connect(lambda: self.action.emit("play", self.task))
        self.btn_primary.clicked.connect(self._on_primary)
        self.btn_folder.clicked.connect(lambda: self.action.emit("folder", self.task))
        self.btn_delete.clicked.connect(lambda: self.action.emit("delete", self.task))
        self.refresh()

    def _on_primary(self) -> None:
        if self.task.state == "failed":
            self.action.emit("retry", self.task)
        else:
            self.action.emit("toggle", self.task)

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        t = self.task
        self.bar.set_value(t.progress)
        self.bar.set_state("downloading" if t.state == "downloading" else
                           ("done" if t.state == "done" else "paused"))
        # 已完成 / 排队中不需要进度条，留着反而像「有东西在跑」
        self.bar.setVisible(t.state in ("downloading", "paused", "failed"))
        # 已完成 / 排队中不需要进度条，留着反而像「有东西在跑」
        self.bar.setVisible(t.state in ("downloading", "paused", "failed"))

        bg, fg, border = STATE_STYLE.get(t.state, STATE_STYLE["paused"])
        self.chip.setText(STATE_TEXT.get(t.state, t.state))
        self.chip.setStyleSheet(
            f"QLabel {{ color: {fg}; background: {bg}; border: 1px solid {border};"
            f" border-radius: 9px; padding: 0 7px; font-size: 10px; }}")

        self.meta.setText(self._meta_text(t))
        color = THEME["danger"] if t.state == "failed" else THEME["text_dim"]
        self.meta.setStyleSheet(f"color: {color}; font-size: 11px;")

        self.btn_primary.setVisible(t.state != "done")
        if t.state == "downloading":
            self.btn_primary.set_icon_name("fa5s.pause")
            self.btn_primary.setToolTip("暂停")
        elif t.state in ("queued", "paused"):
            self.btn_primary.set_icon_name("fa5s.play")
            self.btn_primary.setToolTip("继续下载" if t.state == "paused" else "开始下载")
        elif t.state == "failed":
            self.btn_primary.set_icon_name("fa5s.redo")
            self.btn_primary.setToolTip("重试")
        self.btn_folder.setVisible(t.state == "done")
        self.btn_play.setVisible(t.state == "done")
        self.btn_play.setVisible(t.state == "done")

    @staticmethod
    def _meta_text(t: DownloadTask) -> str:
        if t.state == "failed":
            return f"下载失败 · {t.error or '未知原因'}"
        if t.state == "done":
            return f"已完成 · {format_size(t.bytes_total)} · 已加入本地曲库"
        if t.state == "queued":
            return "排队中 · 等待前面的任务"

        done = format_size(t.bytes_done)
        if t.bytes_total <= 0:
            return f"{t.speed:.1f} MB/s · 已下载 {done}" if t.speed else f"已下载 {done}"
        total = format_size(t.bytes_total)
        if t.state == "paused":
            return f"已暂停 · {done} / {total}"
        return f"{t.speed:.1f} MB/s · {done} / {total} · {t.percent}%"


MAX_ROWS = 80      # 列表一次最多渲染多少行


class DownloadPage(BasePage):
    FILTERS = ("全部", "下载中", "已完成", "失败")

    #: 某个任务下载完成（主窗口据此决定要不要提示）
    finished = pyqtSignal(object)
    #: 删掉了一个任务（可能连文件一起），主窗口据此停播 / 刷新本地曲库
    taskDeleted = pyqtSignal(object, bool)      # (track, deleted_file)

    def __init__(
        self,
        player: Player,
        service: DownloadService,
        settings: SettingsStore,
        parent: QWidget | None = None,
    ):
        super().__init__(parent=parent)
        self.player = player
        self.service = service
        self.settings = settings
        self._tasks: list[DownloadTask] = service.tasks()
        self._filter = 0
        self._rows: list[DownloadRow] = []
        self._notice_shown = False
        self._notice_pending = False

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

        # ---------- 首次声明 ----------
        self.notice = InlineBanner()
        self.notice.dismissed.connect(self._on_notice_dismissed)
        self.body.addWidget(self.notice)

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
        self.lbl_path = QLabel(str(settings.download_dir))
        ph.addWidget(self.lbl_path)
        path_chip.setFixedHeight(30)
        path_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        path_chip.setToolTip("点击更换下载目录")
        path_chip.mouseReleaseEvent = lambda e: self._choose_dir()
        bh.addWidget(path_chip)

        self.btn_all = QPushButton("全部暂停")
        self.btn_all.setObjectName("SmallPill")
        self.btn_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_all.clicked.connect(self._toggle_all)
        self.btn_clear = QPushButton("清空已完成")
        self.btn_clear.setObjectName("SmallPill")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.clicked.connect(self._clear_done)
        bh.addWidget(self.btn_all)
        bh.addWidget(self.btn_clear)
        self.body.addWidget(bar)

        # ---------- 搜索 / 排序 ----------
        tools = QWidget()
        th = QHBoxLayout(tools)
        th.setContentsMargins(0, 0, 0, 0)
        th.setSpacing(8)
        self.search = QLineEdit()
        self.search.setObjectName("SearchInput")
        self.search.setPlaceholderText("搜索任务：歌名 / 歌手")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(30)
        self.search.textChanged.connect(lambda _: self._rebuild())
        th.addWidget(self.search, 1)

        self.sort_box = RoundedCombo()
        style_combo(self.sort_box)
        self.sort_box.addItems(["最近添加", "按歌名", "按大小", "按状态"])
        self.sort_box.setFixedWidth(120)
        self.sort_box.setFixedHeight(30)
        self.sort_box.currentIndexChanged.connect(lambda _: self._rebuild())
        th.addWidget(self.sort_box)
        self.body.addWidget(tools)

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

        # ---------- 服务事件 ----------
        service.taskAdded.connect(self._on_task_added)
        service.taskChanged.connect(self._on_task_changed)
        service.taskRemoved.connect(self._on_task_removed)
        service.taskFinished.connect(self._on_task_finished)
        service.errorRaised.connect(self._on_service_error)

        self._coalescer = Coalescer(self._flush_rebuild, delay_ms=80)
        self.set_filter(0)

    # ---------------- 对外 ----------------
    def enqueue_tracks(self, tracks: list[Track]) -> int:
        """把曲目加进下载队列，返回真正新增的数量。"""
        if not tracks:
            return 0
        added = self.service.enqueue_many(
            tracks, quality=self.settings.download_quality.value)
        if added:
            self._tasks = self.service.tasks()
            self._rebuild()
        return added

    def set_download_dir(self, path: str) -> None:
        self.lbl_path.setText(path)

    # ---------------- 过滤 / 重建 ----------------
    def _choose_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "选择下载目录",
                                                  str(self.settings.download_dir))
        if chosen:
            self.settings.set("download_dir", chosen)
            self.set_download_dir(chosen)

    def _filtered(self) -> list[DownloadTask]:
        tasks = self._sorted()
        keyword = self.search.text().strip().lower() if hasattr(self, "search") else ""
        if keyword:
            tasks = [t for t in tasks
                     if keyword in t.track.title.lower() or keyword in t.track.artist.lower()]
        if self._filter == 0:
            return tasks
        if self._filter == 1:
            return [t for t in tasks if t.state == "downloading"]
        if self._filter == 2:
            return [t for t in tasks if t.state == "done"]
        return [t for t in tasks if t.state in ("failed", "paused", "queued")]

    def _sorted(self) -> list[DownloadTask]:
        tasks = list(self._tasks)
        index = self.sort_box.currentIndex() if hasattr(self, "sort_box") else 0
        if index == 1:
            tasks.sort(key=lambda t: t.track.title)
        elif index == 2:
            tasks.sort(key=lambda t: t.bytes_total, reverse=True)
        elif index == 3:
            tasks.sort(key=lambda t: t.state)
        else:
            tasks.sort(key=lambda t: t.id, reverse=True)
        return tasks

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
                # 先摘父级再 deleteLater：否则旧行（尤其是空态提示）会在
                # DeferredDelete 被处理前继续画在列表上
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self._rows.clear()

        tasks = self._filtered()
        if not tasks:
            empty = QLabel("还没有下载任务" if not self._tasks else "这个分类下还没有任务")
            empty.setObjectName("BodyText")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setFixedHeight(140)
            self._list.addWidget(empty)
        else:
            # 一次最多建 80 行：任务表上千条时逐个建控件会卡死界面
            for t in tasks[:MAX_ROWS]:
                row = DownloadRow(t)
                row.action.connect(self._on_action)
                self._list.addWidget(row)
                self._rows.append(row)

            if len(tasks) > MAX_ROWS:
                more = QLabel(f"还有 {len(tasks) - MAX_ROWS} 条未显示，用搜索或筛选缩小范围")
                more.setObjectName("BodyText")
                more.setAlignment(Qt.AlignmentFlag.AlignCenter)
                more.setFixedHeight(60)
                self._list.addWidget(more)

        self._update_summary()

    def _update_summary(self) -> None:
        running = sum(1 for t in self._tasks if t.state in ("downloading", "queued"))
        paused = sum(1 for t in self._tasks if t.state == "paused")
        done = sum(1 for t in self._tasks if t.state == "done")
        failed = sum(1 for t in self._tasks if t.state == "failed")
        used = sum(t.bytes_done for t in self._tasks)
        total = sum(t.bytes_total for t in self._tasks)

        if not self._tasks:
            self.sub.setText("还没有下载任务。在歌单页点「下载」，或从搜索结果里选一首。")
        else:
            bits = [f"{running} 个任务进行中"]
            if paused:
                bits.append(f"{paused} 个已暂停")
            bits.append(f"已完成 {done} 首")
            if failed:
                bits.append(f"{failed} 个失败")
            bits.append(f"占用 {format_size(used)} / {format_size(total)}")
            self.sub.setText(" · ".join(bits))
        self.btn_all.setText("全部暂停" if running else "全部开始")

    # ---------------- 操作 ----------------
    def _row_for(self, task_id: int) -> DownloadRow | None:
        return next((r for r in self._rows if r.task.id == task_id), None)

    def _on_action(self, action: str, task: DownloadTask) -> None:
        if action == "toggle":
            if task.state in ("queued", "downloading"):
                self.service.pause(task.id)
            else:
                self.service.resume(task.id)
        elif action == "retry":
            self.service.retry(task.id)
        elif action == "delete":
            self._delete_one(task)
        elif action == "play":
            self._play_local(task)
        elif action == "folder":
            self._open_folder(task)

    # ---------------- 删除 ----------------
    def _confirm(self, title: str, text: str, *, has_file: bool) -> tuple[bool, bool]:
        """返回 (是否确认, 是否同时删文件)。没有文件时第二个值恒为 False。"""
        return confirm(
            self, title, text, level="warning", ok_text="删除",
            checkbox="同时删除本地文件（移到回收站）" if has_file else None,
        )

    def _delete_one(self, task: DownloadTask) -> None:
        exists = Path(task.file_path).exists()
        ok, with_file = self._confirm(
            "删除任务",
            f"删除「{task.track.title}」？" + ("\n\n文件：\n" + task.file_path if exists else ""),
            has_file=exists,
        )
        if not ok:
            return
        self.service.delete(task.id, delete_file=with_file)
        self.taskDeleted.emit(task.track, with_file)

    def _clear_done(self) -> None:
        done = [t for t in self._tasks if t.state == "done"]
        if not done:
            self.banner_hint("没有已完成的任务")
            return
        ok, with_file = self._confirm(
            "清空已完成",
            f"清空 {len(done)} 条已完成记录？",
            has_file=any(Path(t.file_path).exists() for t in done),
        )
        if not ok:
            return
        # 只发一次批量信号：逐条发会让主窗口逐条刷新本地曲库（300 次扫描）
        self.taskDeleted.emit([t.track for t in done], with_file)
        self.service.delete_many([t.id for t in done], delete_file=with_file)
        self.banner_hint(f"已删除 {len(done)} 条记录" + ("（含本地文件）" if with_file else ""))

    def banner_hint(self, text: str) -> None:
        """页面内的轻提示（没有全局 banner 时用它）。"""
        self.sub.setText(text)

    def _play_local(self, task: DownloadTask) -> None:
        path = Path(task.file_path)
        if not path.exists():
            self.notice.show_message("文件不在了，可能被移动或删除", level="error",
                                     timeout_ms=5000)
            return
        self.player.play_file(task.track, str(path))

    def _open_folder(self, task: DownloadTask) -> None:
        path = Path(task.file_path)
        target = path if path.exists() else path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _toggle_all(self) -> None:
        if any(t.state in ("queued", "downloading") for t in self._tasks):
            self.service.pause_all()
        else:
            self.service.resume_all()

    # ---------------- 服务事件 ----------------
    def _on_task_added(self, task: DownloadTask) -> None:
        self._tasks = self.service.tasks()
        self._schedule_rebuild()

    def _schedule_rebuild(self) -> None:
        """合并高频刷新：批量删除 300 条会连发 300 个 taskRemoved，
        每次重建都要建 80 个行控件——不合并就是 O(n²)，界面直接卡死。"""
        self._coalescer.trigger()

    def _flush_rebuild(self) -> None:
        self._tasks = self.service.tasks()
        self._rebuild()

    def _on_task_changed(self, event: DownloadEvent) -> None:
        task = next((t for t in self._tasks if t.id == event.task_id), None)
        if task is None:
            return
        if task in self._filtered():
            row = self._row_for(task.id)
            if row is not None:
                row.refresh()
                self._update_summary()
            else:
                self._rebuild()
        else:
            self._rebuild()      # 状态变了，已经不属于当前筛选

    def _on_task_removed(self, task_id: int) -> None:
        self._tasks = self.service.tasks()
        self._schedule_rebuild()
        self._rebuild()

    def _on_task_finished(self, task: DownloadTask) -> None:
        self.finished.emit(task)

    def _on_service_error(self, message: str) -> None:
        self.notice.show_message(message, level="error", timeout_ms=6000)

    # ---------------- 首次声明 ----------------
    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._notice_shown or self.settings.first_run_notice_seen:
            return
        self._notice_shown = True
        self._notice_pending = True
        self.notice.show_message(NOTICE_TEXT, level="warning", action_text="我已知晓")
        write_notice_file(Path(self.settings.download_dir))

    def _on_notice_dismissed(self) -> None:
        if self._notice_pending:
            self._notice_pending = False
            self.settings.set("first_run_notice_seen", True)
