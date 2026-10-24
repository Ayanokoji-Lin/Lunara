# Lunara 架构说明

> 深空、星轨、月光。基于 PyQt6 的沉浸式音乐播放器。
> 信息架构参考网易云 PC 端，视觉语言完全重写（星夜紫 / 月光银 / 深空黑）。

---

## 1. 目录结构

```
Lunara/
├─ main.py                  入口：QApplication、Fusion 样式、QSS 注入、字体
├─ requirements.txt
├─ lunara/
│  ├─ theme.py              THEME 令牌（暗/亮）+ 全局 QSS 模板 + METRICS
│  ├─ assets.py             程序化封面生成、圆角/裁切、QGraphicsBlurEffect 离线模糊
│  ├─ data.py               Track / Playlist 数据类 + 演示曲库 + 歌词
│  ├─ main_window.py        无边框主窗口，四模块装配、导航历史、快捷键
│  ├─ core/player.py        播放内核（虚拟时钟，可平滑替换为 QMediaPlayer）
│  ├─ widgets/
│  │  ├─ icons.py           qtawesome 封装 + 无依赖降级
│  │  ├─ common.py          IconButton / SectionHeader / Chip / 多行文本绘制
│  │  ├─ cover.py           CoverArt、CoverCard（自绘卡片）、ShadowBox
│  │  ├─ banner.py          BannerCarousel（淡入淡出 + 渐变遮罩）
│  │  ├─ sidebar.py         LogoMark、SidebarItem（3px 指示条）、折叠分组
│  │  ├─ topbar.py          搜索框、用户区、窗口控制、startSystemMove 拖动
│  │  ├─ player_bar.py      80px 播放栏
│  │  ├─ seek_slider.py     可点击跳转的 QSlider
│  │  ├─ vinyl.py           VinylDisc（QPropertyAnimation 旋转）
│  │  ├─ lyrics.py          LyricView（平滑居中滚动）
│  │  ├─ track_table.py     TrackModel + TrackDelegate + TrackTable
│  │  ├─ toggle.py          Switch（胶囊开关，滑块动画）
│  │  ├─ wave.py            WaveBars（跳动音波）
│  │  ├─ progress.py        ThinProgress（细进度条 + 下载流光）
│  │  └─ starfield.py       StarField（星光粒子）
│  └─ pages/
│     ├─ base.py            BasePage（自适应版心 + QScrollArea）、EmptyPage
│     ├─ home.py            首页：Banner + 推荐歌单网格 + 新歌速递
│     ├─ playlist.py        歌单详情：信息头 + 歌曲表
│     ├─ now_playing.py     播放页：三模式（唱片/纯歌词/纯封面）
│     ├─ search.py          搜索：Tab + 单曲列表 / 网格
│     ├─ download.py        本地下载：任务行 + 筛选 + 批量控制
│     └─ settings.py        设置：左导航 + QStackedWidget
└─ tools/shoot.py           离屏截图脚本（视觉走查用）
```

---

## 2. 类结构与职责

```
MainWindow(QWidget, 无边框)
├─ player: Player(QObject)            播放状态中枢（唯一数据源）
├─ sidebar: Sidebar(QFrame)           导航，navigate(key) 信号
├─ topbar: TopBar(QFrame)             搜索 / 窗口控制 / 拖动
├─ stack: QStackedWidget              页面容器（只创建一次，靠索引切换）
│   ├─ 0 HomePage       playlistActivated(int)
│   ├─ 1 PlaylistPage   set_playlist(Playlist, tracks?, title?)
│   ├─ 2 SearchPage     search(text)
│   ├─ 3 SettingsPage   switch(index)
│   ├─ 4 NowPlayingPage backRequested()
│   ├─ 5 EmptyPage      configure(title, hint, icon)
│   └─ 6 DownloadPage   set_filter(0..3)
└─ player_bar: PlayerBar(QFrame)      openNowPlaying() 信号
```

### 职责边界

| 类 | 只做一件事 | 关键接口 |
|---|---|---|
| `Player` | 队列、进度、模式、喜欢；不碰任何 UI | `set_queue / play_track / toggle / seek / cycle_mode` |
| `MainWindow` | 装配 + 导航路由 + 窗口行为 | `navigate(key) / open_playlist / _apply_window_state` |
| `Sidebar` | 导航条目与选中态 | `navigate(str)`、`select(key)` |
| `TopBar` | 搜索输入、窗口按钮、拖动 | `searchSubmitted / minimizeRequested …` |
| `PlayerBar` | 播放控制与进度回显 | `openNowPlaying` |
| `NowPlayingPage` | 三种沉浸模式 + 模糊背景 | `set_mode(0/1/2)` |
| `CoverCard` | 一张封面卡（自绘，无子控件） | `clicked / playClicked` |
| `TrackTable` | 歌曲列表（Model/View） | `trackActivated(Track)` |
| `DownloadPage` | 下载任务总览与操作 | `set_filter`、`DownloadRow.action` |
| `assets` | 图像生成与模糊（纯函数 + 缓存） | `cover_pixmap / blurred_background` |
| `theme` | 令牌与 QSS（`string.Template` 注入） | `qss()` |

### 信号流向

```
Sidebar.navigate ─┐
HomePage.playlistActivated ─┼→ MainWindow 路由 → stack.setCurrentIndex
TopBar.searchSubmitted ────┘

Player.trackChanged ──→ PlayerBar / PlaylistPage.table / NowPlayingPage
Player.positionChanged ─→ PlayerBar.seek / LyricView.set_position
Player.playingChanged ──→ VinylDisc.start/stop + 播放键图标
Player.likeChanged ─────→ 喜欢按钮颜色
```

单向依赖：**UI → Player → data**。页面之间不互相引用，全部通过 `MainWindow` 路由。

---

## 3. 无边框窗口骨架

`lunara/main_window.py`：

```python
self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
self.setMinimumSize(1056, 752)

self._outer = QVBoxLayout(self)                    # 四周留 18px 给阴影
self._outer.setContentsMargins(18, 18, 18, 18)
self.root = QWidget(); self.root.setObjectName("WindowRoot")   # 圆角 + 背景

shadow = QGraphicsDropShadowEffect(self.root)      # 模糊 20 / 偏移 (0,8) / rgba(0,0,0,100)
shadow.setBlurRadius(20); shadow.setOffset(0, 8)
shadow.setColor(QColor(0, 0, 0, 100))
self.root.setGraphicsEffect(shadow)
```

布局嵌套（与网易云一致的四模块）：

```
QVBoxLayout(outer)
└─ WindowRoot
   ├─ QHBoxLayout(body)
   │  ├─ Sidebar(204, 撑满高度)
   │  └─ QVBoxLayout
   │     ├─ TopBar(56)
   │     └─ ContentArea → QStackedWidget(自适应)
   └─ PlayerBar(80)
```

拖动没有自己算 `globalPos`，而是交给系统（多屏 / 高 DPI 更稳）：

```python
def mousePressEvent(self, e):                    # TopBar
    if e.button() == Qt.MouseButton.LeftButton:
        self.window().windowHandle().startSystemMove()
```

缩放用 `QSizeGrip` 挂在右下角（无边框窗口必须自己挂），最大化时隐藏并去掉阴影与外边距：

```python
m = 0 if maximized else 18
self._outer.setContentsMargins(m, m, m, m)
self.root.setProperty("windowState", "maximized")   # QSS 里去掉圆角
self._shadow.setEnabled(not maximized)
```

---

## 4. 全局 QSS

`lunara/theme.py` 用 `string.Template`（而不是 f-string）注入，避免 QSS 的 `{}` 与 Python 格式化冲突：

```python
THEME = {"primary": "#8B5CF6", "bg_main": "#0F172A", "bg_panel": "#1E293B", ...}
_QSS = Template("""
QPushButton#SidebarItem:checked { background-color: $bg_active; color: $text_main; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.15); border-radius: 4px; }
""")
def qss(theme=None): return _QSS.substitute(dict(theme or THEME, font_ui=FONT_UI))
```

已覆盖：侧边栏各状态、列表行悬停（delegate 自绘）、输入框 focus、进度条槽/手柄、胶囊开关（QSS + 自绘两套）、菜单、表头、下拉框，以及滚动条极限美化（宽 8px、全透明轨道、`add-line/sub-line` 高度 0）。

**滚动条**

```css
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px 0; border: none; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.15); border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.30); }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; background: transparent; border: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
```

---

## 5. 关键特效实现

### 5.1 唱片旋转（20s/圈，暂停可续）

```python
self._anim = QPropertyAnimation(self, b"angle", self)
self._anim.setStartValue(0.0); self._anim.setEndValue(360.0)
self._anim.setDuration(20000); self._anim.setLoopCount(-1)
self._anim.setEasingCurve(QEasingCurve.Type.Linear)

angle = pyqtProperty(float, fget=get_angle, fset=set_angle)

def start(self):
    if self._anim.state() == QAbstractAnimation.State.Paused:
        self._anim.resume()          # 续播，角度连续
    elif self._anim.state() != QAbstractAnimation.State.Running:
        self._anim.start()

def stop(self):
    if self._anim.state() == QAbstractAnimation.State.Running:
        self._anim.pause()           # 不要 stop()，否则角度归零
```

绘制时只旋转封面与内圈，纹路/外环不旋转（视觉等价且省绘制）。

### 5.2 播放页高斯模糊背景

`QGraphicsBlurEffect` 不能直接挂在会被频繁 resize 的 QLabel 上（每次重排都重算模糊）。这里用「缩小 → 模糊 → 放大」的离线方案：

```python
small = pm.scaled(int(w*0.32), int(h*0.32), IgnoreAspectRatio, SmoothTransformation)
scene = QGraphicsScene(); item = QGraphicsPixmapItem(small)
effect = QGraphicsBlurEffect()
effect.setBlurRadius(radius * 0.32)          # 半径同比缩小，视觉等价
effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
item.setGraphicsEffect(effect); scene.addItem(item)
scene.render(painter, QRectF(out.rect()), scene.sceneRect())   # 渲染到 QImage
```

再把结果叠一层 `rgba(15,23,42,0.62)` 遮罩 + 上下渐深，`setPixmap` 到铺满页面的 QLabel（overscan 1.18 倍，避免模糊后边缘透光）。resize 用 110ms 单次定时器防抖。

### 5.3 进度条：点击跳转 vs 拖拽

```python
def mousePressEvent(self, e):
    self._dragging = True
    self.setSliderDown(True)
    self.setValue(self._value_at(e.position().x()))   # 点哪跳哪
def mouseReleaseEvent(self, e):
    self._dragging = False
    self.seekRequested.emit(self.value())             # 松手才真正 seek
def set_progress(self, pos, dur):
    if self._dragging or dur <= 0: return             # 拖动中忽略外部回写，防抖
```

`_value_at` 扣掉手柄宽度：`ratio = (x - HANDLE/2) / (width - HANDLE)`。

### 5.4 歌词平滑居中

每行一个 QLabel，`active` 动态属性切换字号/颜色，滚动用 `QPropertyAnimation` 打在滚动条 `value` 上：

```python
target = lbl.y() + lbl.height()//2 - viewport.height()//2
anim = QPropertyAnimation(self.verticalScrollBar(), b"value")
anim.setDuration(460); anim.setEasingCurve(QEasingCurve.Type.OutCubic)
```

首尾用可伸缩 Spacer 撑开（高度 = 视口一半 - 行高一半），保证第一句和最后一句也能居中；布局变更后用 `QTimer.singleShot(0, ...)` 再取 `lbl.y()`。

### 5.5 下载页

四个状态驱动同一套行组件，避免为每种状态写一份 UI：

```python
STATE_TEXT  = {"downloading": "下载中", "paused": "已暂停",
               "done": "已完成", "failed": "失败"}
STATE_STYLE = {...}   # chip 的 背景/文字/描边 三元组
```

- 进度条是自绘的 `ThinProgress`：轨道 + 填充 + 流光扫过；`QColor` 不认 CSS 的
  `"rgba(...)"` 字符串，颜色必须用 `(r,g,b,a)` 或 `#hex`，否则会渲染成纯黑。
- 状态变化只刷新受影响的那一行（`_refresh_task`），只有离开当前筛选（如失败页点重试）
  才重建列表，避免点击时把正在被点击的 widget 一起销毁。
- 进度由 `QTimer(500ms)` 推进，`isVisible()` 为假时直接 return（切走页面不空转）。
- 目录胶囊、行悬停都用 QSS（`QFrame#PathChip` / `QFrame#DownloadRow:hover`），
  不给容器设内联 `background`，避免样式级联吃掉子控件状态。

### 5.6 列表行悬停 / 播放行音波

行背景在 `TrackTable.paintEvent` 里整行铺底（逐格画会出现接缝），文字与序号列由 `TrackDelegate` 绘制：

```python
def paintEvent(self, event):
    p = QPainter(self.viewport())
    self._paint_row_backgrounds(p)     # 播放行 rgba(139,92,246,30)，悬停行 rgba(51,65,85,105)
    p.end()
    super().paintEvent(event)
```

播放行的音波用 110ms 定时器推进相位，只 `viewport().update(序号列矩形)`，开销可忽略。

---

## 6. 踩过的坑（Qt 6.11 / Windows）

1. **`border-radius` ≥ 控件半高时圆角会被整体丢弃**。`radius: 20px` 在 36px 高的胶囊按钮上会变成直角方块；改成 17px 即恢复。所有胶囊/圆形控件都按 `radius < height/2` 取值。
2. **父级挂了 `QGraphicsEffect`，子级的 `QGraphicsDropShadowEffect` 不渲染**。主窗口必须有悬浮阴影，所以封面阴影改用「画圆角矩形 → 模糊成贴图」的 `ShadowBox`，Logo 发光改为自绘径向渐变。
3. **QSS 里的 `font-size` 会覆盖 `setFont()`**。全局 `QWidget { font-size: 12px }` 会让所有代码里设的字号失效，正确做法是只设 `font-family`，基准字号交给 `QApplication.setFont()`。
4. **`QScrollArea` 内的容器不要写 `setStyleSheet("background: transparent")`**，该规则会级联到所有子控件，把按钮的 hover 背景一起吃掉；改用 `QSS` 里的 `QScrollArea#PageScroll > QWidget > QWidget` 选择器。
5. **offscreen 平台没有字体回退**，中文会全变方框。视觉走查必须用真实 windows 平台 + `WA_DontShowOnScreen`（见 `tools/shoot.py`）。
6. 样式必须配合 `app.setStyle("Fusion")`，否则 Windows 原生样式的部分绘制会盖过 QSS。

---

## 7. 可行性建议：paintEvent 还是 Delegate？

| 需求 | 方案 | 理由 |
|---|---|---|
| 歌单封面播放量渐变遮罩 | **QPainter（`CoverCard.paintEvent`）** | 遮罩是静态装饰，不需要 item 交互；自绘一张卡片可省掉 3~4 个子控件 |
| 列表行悬停 / 播放行高亮 / 音波 | **QStyledItemDelegate + view.paintEvent 铺底** | 数据驱动样式（哪一行在播放），QSS 无法表达；整行背景必须画在 item 之前 |
| 两行截断的歌单名 | **QTextLayout（`draw_wrapped`）** | QSS/QLabel 只能单行省略，`wordWrap` 又不限行数 |
| Banner 底部渐变 | **QPainter + QLinearGradient** | QSS 的 `qlineargradient` 无法做柔和的 alpha 过渡 |
| 歌词滚动居中 | **QPropertyAnimation + QLabel 动态属性** | 需要缓动与逐行字号变化，QSS 只有离散状态 |
| 胶囊开关 | **自绘 QAbstractButton** | QSS 版只有颜色变化，没有滑块位移动画 |
| 唱片旋转 | **QPropertyAnimation + pyqtProperty** | `QTimer` 手动改角度会掉帧 |
| 圆形/圆角裁剪 | **QPainterPath + setClipPath** | QSS 的 `border-radius` 不裁剪子内容（也不裁剪 pixmap） |
| 细进度条 + 流光 | **自绘 QWidget** | QProgressBar 只能纯色块，且 5px 高度下圆角会被丢 |

---

## 8. 下一步

- **接入真实音频**：`Player._tick` 换成 `QMediaPlayer.positionChanged`，`toggle/seek` 转发到播放器；`Player` 的对外信号保持不变，UI 零改动。
- **曲库落库**：`data.py` 换成 SQLite + `mutagen` 读标签，扫描本地目录。
- **封面缓存**：`assets` 目前是进程内 dict，长期可换 `QPixmapCache`（有容量上限）+ 磁盘缩略图。
- **亮色主题**：`LIGHT` 已备好，`qss(LIGHT)` + `repolish` 即可切换，但 `assets` 里的深空渐变需要按主题调整亮度。
- **打包**：`pyinstaller --noconsole --add-data` 注意把 qtawesome 的字体文件一起打进去。
