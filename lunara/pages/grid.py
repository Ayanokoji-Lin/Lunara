"""通用网格页：播客推荐、首页「更多」都用它。

只负责画卡片与抛事件，点进去做什么由 `MainWindow` 决定（播客是播单集，
歌单「更多」是打开歌单，新歌「更多」是播这一首）。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from ..services.catalog import CardItem
from ..widgets.anim import detach, stagger
from ..widgets.cover import CoverCard
from .base import BasePage


class GridPage(BasePage):
    COLS = 5

    #: 点了某张卡片（参数是 ``CardItem.seed``，调用方自己解释成 id）
    cardActivated = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self._items: list[CardItem] = []
        self._cards: list[CoverCard] = []

        head = QWidget()
        hv = QVBoxLayout(head)
        hv.setContentsMargins(0, 0, 0, 0)
        hv.setSpacing(6)
        self.lbl_title = QLabel("全部")
        self.lbl_title.setObjectName("PageTitle")
        self.lbl_sub = QLabel()
        self.lbl_sub.setObjectName("BodyText")
        hv.addWidget(self.lbl_title)
        hv.addWidget(self.lbl_sub)
        self.body.addWidget(head)

        self._host = QWidget()
        self._grid = QGridLayout(self._host)
        self._grid.setContentsMargins(0, 12, 0, 0)
        self._grid.setHorizontalSpacing(24)
        self._grid.setVerticalSpacing(26)
        for c in range(self.COLS):
            self._grid.setColumnStretch(c, 1)
        self.body.addWidget(self._host)

        self.empty = QLabel("这里还没有内容")
        self.empty.setObjectName("BodyText")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setFixedHeight(140)
        self.body.addWidget(self.empty)

        self.body.addStretch(1)

    # ------------------------------------------------------------------ #
    def configure(self, title: str, subtitle: str, items: list[CardItem],
                  *, empty_text: str = "这里还没有内容") -> None:
        self.lbl_title.setText(title)
        self.lbl_sub.setText(subtitle)
        self._items = list(items)
        self.empty.setText(empty_text)
        self._rebuild()

    def _rebuild(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                detach(widget)
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._cards.clear()

        self._host.setVisible(bool(self._items))
        self.empty.setVisible(not self._items)

        for i, item in enumerate(self._items):
            card = CoverCard(item.seed, item.hue, item.title, item.subtitle, "",
                             cover_url=item.cover_url)
            card.clicked.connect(lambda seed=item.seed: self.cardActivated.emit(seed))
            card.playClicked.connect(lambda seed=item.seed: self.cardActivated.emit(seed))
            self._grid.addWidget(card, i // self.COLS, i % self.COLS)
            self._cards.append(card)

        stagger(self._cards, step=16, duration=220, limit=20)
