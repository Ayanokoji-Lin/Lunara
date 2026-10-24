# Lunara · UI 功能落地计划

> 前提：数据层（api / services / store）已完成，当前 145 项单测 + 5 项真机冒烟通过。
> 本文件回答一个问题：**怎么把 UI 上每一个按钮接到真实数据上**，且不重画界面。
> 歌词与封面确定走官方接口，不接 GD Studio 的 `lyric` / `pic`。

---

## 0. 原则（先定规矩，后面才不跑偏）

1. **视觉零改动**：布局、配色、动效、间距都不动。只允许在页面里**增加数据注入口**。
2. **mock 变兜底**：`lunara/data.py` 保留，断网/未登录时仍能演示，不出现空白页。
3. **UI 只认三个契约**：`Track` / `Playlist` / `DownloadTask`（都在 `data.py`）。
   API 模型一律经 `services/catalog.py` 适配，页面里不出现 `Song` / `SongUrlItem`。
4. **请求一律异步**：页面通过 `QtAsyncBridge.submit()` 拿结果，回调在主线程。
5. **每阶段可独立验收**：做完一个阶段，界面就该有一块是真的，其余仍是 mock，互不阻塞。

---

## 1. 现状盘点（页面 × 功能 × 接口 × 验证状态）

| 页面 | 功能 | 现在 | 需要的接口 | 状态 |
|---|---|---|---|---|
| 首页 | Banner 轮播 | 本地文案 | 保留本地（3 张），点击跳歌单 | 无需接口 |
| 首页 | 推荐歌单 5×2 | `PLAYLISTS` mock | `/api/personalized/playlist` | ✅ 已实测 |
| 首页 | 新歌速递 5 张 | `TRACKS[:5]` | `/api/personalized/newsong` | ✅ 已实测 |
| 歌单详情 | 封面/标题/作者/播放量/描述 | `PLAYLISTS[0]` | `/api/v6/playlist/detail` | ✅ 已实测 |
| 歌单详情 | 曲目列表 | `playlist.tracks` | 同上（`playlist.tracks`） | ✅ 已实测 |
| 歌单详情 | 收藏 / 下载 | 无逻辑 / 跳页 | `/api/playlist/subscribe` | ⬜ 未接（同上） |
| 搜索 | 单曲 | 本地过滤 | `cloudsearch` type=1 | ✅ 已实测 |
| 搜索 | 歌手 | 本地去重 | `cloudsearch` type=100 | ✅ 已实测 |
| 搜索 | 专辑 | 本地去重 | `cloudsearch` type=10 | ✅ 已实测 |
| 搜索 | 歌单 | 本地过滤 | `cloudsearch` type=1000 | ✅ 已实测 |
| 播放页 | 歌词 | `LYRICS` 固定 | `/api/song/lyric` | ✅ 已实测（LRC 文本） |
| 播放页 | 喜欢 | 内存 set | `/api/like` | ⬜ 未接（登录已就绪，写接口待实测） |
| 播放栏 | 播放/进度/音量 | `QMediaPlayer`（真实音频） | `player_url` + 直链注入 | ✅ 已实测 |
| 侧栏 | 我喜欢的音乐 | 真实歌单（456 首） | 走 `specialType=5` 歌单，不用 `/api/song/like` | ✅ 已实测 |
| 侧栏 | 我的歌单 | 真实分组（创建 / 收藏） | `/api/user/playlist` | ✅ 已实测 |
| 下载页 | 任务/进度/暂停 | 真实下载（SQLite 任务表） | `player_url` + HTTP 流式 + Range | ✅ 已实测 |
| 设置 | 音质偏好 | 4 档下拉（只是 UI） | 映射 `QualityLevel` | ⬜ 未接（4 档正好对上，改动很小） |

实测命令：`tools/probe_ui_api.py`（匿名）与 `tools/probe_account_api.py`（登录态）。

---

## 2. 分阶段计划

| 阶段 | 状态 | 验收方式 |
|---|---|---|
| P0 适配层 | ✅ 完成 | 适配层单测全绿（13 组真实回包夹具，当前共 145 项） |
| P1 首页 | ✅ 完成 | `tools/verify_ui_live.py` 打出 10 张真实歌单 + 5 首新歌 |
| P2 歌单详情 | ✅ 完成 | 同一脚本打开热歌榜，200 首真实曲目 |
| P3 搜索四类 | ✅ 完成 | 四个 Tab 全部真实结果（30 单曲 / 20 歌手 / 20 专辑 / 20 歌单） |
| P3.5 真实封面 | ✅ 完成 | 首页/歌单/搜索/播放页都是真图，拿不到时回落月牙空态 |
| P4 歌词 | ✅ 完成（音频待单独一轮） | 热歌榜首曲 101 行真实歌词，时间轴与虚拟时钟对齐 |
| P5a 登录 | ✅ 完成 | 内嵌浏览器登录 → 抓 Cookie → DPAPI 加密落盘 |
| P5b 我的音乐 | ✅ 完成 | 侧栏 6 个真实歌单；「我喜欢的音乐」456 首 |
| P6 下载 | ✅ 完成 | 真实文件落盘、暂停续传、重启恢复、并发上限 |
| P6.5 音频内核 | ✅ 完成 | 真实出声、真实时长、seek、切歌竞态 |
| P6.5 音频内核 | ✅ 完成 | 真实出声、真实时长、seek、切歌竞态 |
| P7 收尾 | ✅ 完成 | 音质接线、错误细条、首页失败重试 |
| P8 歌手页 / 专辑页 | ✅ 完成 | 搜「周杰伦」点卡片：50 首热门 / 13 首专辑曲目 |

> P9–P13（喜欢同步、搜索分页、本地播放、亮色主题、打包）记录在 `docs/PLAN-REMAINING.md`。

### P0 · 适配层与模块（无 UI 改动）✅

**做了什么**
- `services/catalog.py`：`to_track(Song) -> Track`、`to_playlist(PlaylistDetail) -> Playlist`、
  `to_playlist_card(RecommendedPlaylist)`、`to_track_from_newsong(NewSongEntry)`。
  - `Track.hue` 由 `id` 派生（`id * 37 % 360`），保证同一首歌封面稳定，不依赖接口。
- 新模块：`api/modules/playlist.py`（详情）、`api/modules/lyric.py`、`api/modules/personalized.py`。
- 新模型：`PlaylistDetail` / `LyricResponse` / `RecommendedPlaylist` / `NewSongEntry`。
- LRC 解析：`services/lyrics.py`，`[mm:ss.xxx]` → `list[(ms, text)]`，跳过空行、去重、排序。
- `data.py` 的 `Playlist` 增加 `desc` 字段（真实简介），空值时页面仍用原默认文案。

**验收**：`tests/test_catalog.py`、`tests/test_lyrics.py`、`tests/test_modules_ui.py` 全绿。

### P1 · 首页接真 ✅

**UI 改动（只加方法）**：`HomePage.set_playlists()` / `set_new_songs()`，
把 `__init__` 里建网格的代码抽成 `_rebuild_playlists()` / `_rebuild_songs()`，卡片逻辑一行未改。

**接线**：`MainWindow` 用 `QTimer.singleShot(0, ...)` 启动后异步拉两个接口
（`asyncio.gather` 并发），成功后注入；失败只记一条 warning，界面继续用演示数据。

**验收**：`tools/verify_ui_live.py` 输出 10 张真实歌单（含播放量）与 5 首新歌，
截图 `shots/12_home_live.png` 与改前 `shots/01_home.png` 布局一致。

### P2 · 歌单详情 ✅

**UI 改动**：无（`PlaylistPage.set_playlist(playlist, tracks, title)` 已存在）。

**接线**：`MainWindow.open_playlist(pid)` → 异步 `/api/v6/playlist/detail` → `catalog.to_playlist` → `set_playlist`。
加载期间沿用现有页面（显示上一次内容），避免闪烁。

**验收**：任意歌单 id 能打开，曲目数与线上一致，「播放全部」可用。

### P3 · 搜索四类 ✅

**UI 改动**：`SearchPage.set_results(payload, keyword)` + `resultsRequested` 信号；
本地过滤保留为兜底（敲字立刻有反应），真实结果到了再覆盖。

**接线**：
- 输入 320ms 防抖（`MainWindow._search_timer`）→ 只打**当前 Tab** 那一个 `type`；
- 切 Tab 时若 `(关键词, Tab)` 没拉过 → 发 `resultsRequested` 补一次（每类最多一次，另有 5 分钟列表缓存）；
- 关键词已变时丢弃迟到的结果（`set_results` 里比对 keyword），避免慢请求盖掉新结果。

**实测**：搜「周杰伦」→ 单曲 30 / 歌手 20 / 专辑 20 / 歌单 20，四类都有真实数据，
截图 `shots/14_search_songs.png`、`15_search_artists.png`。

**已知缺口**：歌手页 / 专辑页还没有，卡片点击暂时播当前结果的第一首（占位）。
这两个详情接口尚未实测，等做它们时再补。

### P3.5 · 真实封面 ✅

**规则（按你的补充）**：**月牙 = 空态**。有真实封面就显示图，没有（还没下载完 / 下载失败 / 接口没给）
才回落到程序化月牙封面。

**做了什么**
- `services/covers.py`：异步下载 + 磁盘缓存（`%APPDATA%/Lunara/covers/<sha1>.img`）+ 内存 LRU；
  同一个 seed 只下载一次；下载线程只回传 bytes，`QPixmap` 解码留在主线程。
- `CoverArt` / `CoverCard` / `VinylDisc` 都支持 `cover_url`，收到 `ready(seed)` 信号后自动重绘。
- `Track` / `Playlist` / `CardItem` 增加 `cover_url`，由 `catalog` 从 `album.picUrl` /
  `coverImgUrl` 填进来。
- 首页、歌单页、搜索三类卡片、播放页（大封面 + 黑胶中心）全部生效。

**验收**：`shots/12_home_live.png` 十张真实封面；`16_now_playing_live.png` 黑胶中心是真实专辑图。

### P4 · 歌词 ✅（音频留到单独一轮）

> 已定：**先保留虚拟时钟**，等数据全部接完再换 `QMediaPlayer`。所以本轮只接歌词，
> 播放内核不动，`core/player.py` 一行不改。

**歌词**：`NowPlayingPage.set_lyrics()`；`MainWindow` 监听 `player.trackChanged` →
异步拉 `/api/song/lyric` → `parse_lyric_response` → 注入；空歌词保持演示歌词，切歌不闪白。

**顺带修的老问题**：`LyricView.set_lyrics` 原来只 `deleteLater()`，旧行在事件循环处理
DeferredDelete 前仍留在视口里——换歌词瞬间会看到「两列歌词」。改成先 `hide()` +
`setParent(None)` 再删除。

**播放（后续单独一轮）**：`core/player.py` 换 `QMediaPlayer` + `PlayerUrlService`；
`trial=True` 时发 `trialModeChanged` 信号（标题旁加「试听」小字）。

**验收**：热歌榜首曲《我不难过》拉到 101 行真实歌词（`[0s] 作词 : 杨明学` …），
截图 `shots/16_now_playing_live.png`。

### P5a · 登录 ✅

**登录方案（已定）**：**不碰登录接口，直接开浏览器让用户自己登，然后取 Cookie 加密存本地。**

**落地**
- `services/login_browser.py`：`QWebEngineView` 打开 `music.163.com/#/login`，
  监听 `cookieStore().cookieAdded`，只收 `.music.163.com` 域，出现 `MUSIC_U` 即成功并自动关闭。
- `services/secret_store.py`：Windows 优先 **DPAPI**（`CryptProtectData`，密钥由系统按用户托管），
  不可用时退回 AES-256-GCM（密钥来自 `LUNARA_SECRET_KEY` 或本地 `key.bin`）。
  文件格式 `LNR1` + 模式字节 + 载荷；损坏/换账户一律返回 `None`，回落未登录。
- `services/account.py`：只存 `MUSIC_U` / `__csrf` / `NMTID` 三个键，其余丢弃。
- 设置页新增「账号」页：状态文案 + 登录/退出按钮；主窗口启动时自动恢复登录态。
- `main.py` 在 QApplication 之前设 `AA_ShareOpenGLContexts`，并把 `HTTPS_PROXY` 桥接成
  Chromium 的 `--proxy-server`（Windows 上 Chromium 不读这些环境变量）。

**验证**
- `tests/test_secret_store.py`（9 项，含「明文不在磁盘上」「密文被篡改」）
- `tests/test_account.py`（8 项，白名单 / 落盘恢复 / 退出清理）
- `tools/smoke_login.py`：真实加载登录页，实测收到 `JSESSIONID-WYYY` 等 Cookie
- `shots/17_settings_account.png`：账号面板

**已知环境限制**：本机无 GPU 上下文时 Chromium 会加载失败，
需 `QT_OPENGL=software`（登录窗口里已内置这条提示）。

### P5b · 我的音乐 ✅

**实测（2026-10-24，登录态，uid 9605257338）**
- `/api/user/playlist` → `playlist[]`（12 个，含 `specialType` / `subscribed` / `creator`）；
- `/api/song/like` → **eapi 下 code=400**（uid 传 int 或 str 都一样，疑似仅 weapi 支持），
  所以「我喜欢的音乐」改走**歌单**：它本身就是 `specialType=5` 的特殊歌单，详情接口照常给 456 首。
- 坑：收藏别人的「喜欢的音乐」也是 `specialType=5`，必须靠 `subscribed` 区分，
  否则 `liked_id` 会指到别人歌单上（实测踩到过）。

**接线**
- `api/modules/user.get_user_playlists()` + `models.user.UserPlaylist`；
- `catalog.split_user_playlists()` →（创建的、收藏的、我喜欢的 id）；
- `Sidebar.set_my_playlists()` 重建「创建的歌单 / 收藏的歌单」两组，key 用 `myplaylist:<id>`；
- `MainWindow.navigate()` 支持 `myplaylist:<id>`；`liked` 有真实 id 就打开那个歌单，没有则回落演示数据；
- 退出登录恢复演示分组。

**顺带修的**
- `PlaylistDetail.description` / `creator.nickname` 可能是 `null` → 模型容忍，简介不再硬编码兜底
  （演示歌单的简介改由 `data.py` 提供）；
- 侧栏歌单名过长 → 按 150px 省略 + `setToolTip` 显示全名。

**验收**：截图 `shots/18_sidebar_mine.png`、`19_liked_playlist.png`。

### P6 · 下载 ✅

**落地**
- `services/download/naming.py`：文件名清洗（非法字符 / 保留名 / 长度 / 重名）、
  扩展名推断（URL → Content-Type → 档位）、`Content-Range` 解析；
- `services/download/store.py`：SQLite 任务表（WAL、`song_id` 唯一、损坏自愈），
  启动时把 `downloading` 改回 `queued` 实现崩溃恢复；
- `services/download/service.py`：调度器限流（可实时改并发）、流式 Range 续传、
  暂停/恢复/删除、4Hz 进度信号、速度 EWMA；
- `services/settings_store.py` + `services/paths.py`：设置落盘（原子写、损坏回默认），
  下载目录 / 并发 / 完成提示 / 音质 / 首次声明已读；
- `widgets/notice.py`：`InlineBanner`（错误、完成提示、首次声明共用）；
- 页面：`DownloadPage` 去掉 `QTimer`，改为订阅服务事件；`queued` 状态、空态、
  真实封面、打开文件夹；歌单页「下载」改为带上曲目；设置页三控件与音质下拉接线。

**关键取舍**
- **`trial=True` 一律失败**：宁可报错，也不把 45 秒试听存成整首。
- **`bytes_done` 以 `.part` 实际大小为准**，不用内存计数器（取消/强杀时不漂移）。
- **不用固定 `Semaphore`**：设置页要能实时改并发，改用「调度器 + 整数上限」。

**验收**：两首真实歌曲下载完成（36.1 MB / 37.6 MB FLAC，文件头校验通过），
截图 `shots/20_download_live.png`；暂停/续传/416/403/5xx/并发上限等 10 个场景有单测覆盖。

### P6.5 · 音频内核替换 ✅

**做法：双引擎，对外契约不变**
- `Player(engine="auto"|"media"|"clock")`：能建 `QMediaPlayer` 就用 media，
  否则退时钟（无音频设备、测试、演示曲目）。
- `Track.remote` 区分线上曲目与 `data.py` 的演示曲目：演示曲目永远走时钟，不联网。
- 6 个信号 + 8 个方法签名一个没改，页面零改动（只修了 `PlayerBar._on_seek` 用真实时长）。

**异步直链怎么接**
```
play() → urlRequested(seq, track) → MainWindow 用 QtAsyncBridge 调 PlayerUrlService
       → set_source(seq, url, trial) 或 resolve_failed(seq, msg)
```
`seq` 单调递增，`set_source` 里比对，迟到结果直接丢——连续切歌不串台。

**踩到的坑**
- `_load_current` 里又请求了一次直链，和 `play()` 重复 → 改成只清音源，请求统一由 `play()` 触发。
- `seek` 原来用 `track.duration_ms` 钳制，真实时长比接口值长/短时会跳错位置 → 统一走 `Player.duration_ms`。
- `QMediaPlayer` 首帧要缓冲，连切后 2 秒内 `position` 还是 0 属正常，别误判成卡住。

**验收**：热歌榜首曲真实播放，时长 320.4s（接口 320s），3 秒后位置 1228ms，
seek 到 160222ms 实际落在 160654ms，暂停生效；截图 `shots/21_playing_live.png`。
另有 15 项内核逻辑单测（时钟推进、单曲循环、连切竞态、试听标记）。

### P7 · 收尾 ✅

- **音质偏好接线**：设置页 4 档下拉 → `QualityLevel`，播放走 `play_quality`、下载走 `download_quality`；
  `hires / jymaster` 不暴露（GD 的 999 已把三档合并成同一文件）。
- **统一错误呈现**：`MainWindow._show_error()` → 内容区顶部 `InlineBanner`（6 秒自动消失、可手动关闭），
  首页 / 歌单 / 搜索 / 播放失败全部走它，不弹窗。
- **首页失败自动重试一次**（3 秒后），仍失败就继续用演示数据并保留提示条。
- **登录态共享**：`MainWindow` 只建一个 `SessionService` 注入 `PlayerUrlService`，
  登录/退出立刻影响播放与下载的会员判定（不会再各自缓存 30 秒旧值）。
- **试听标注**：`trialModeChanged(True)` → 提示条「只提供 45 秒试听片段」。

> 文档不再单独写 `README-api.md`：数据层记录在 `docs/API-PLAN.md`，接线记录在本文，架构在 `docs/ARCHITECTURE.md`。

**顺带修掉的重复连接**：`player.urlRequested` 曾被连接两次（一次播放解析两次），
`tools/verify_error_bar.py` 里加了「一次播放只解析一次」的回归断言。

**验收**：`shots/22_error_bar.png`（错误只出现在顶部细条，页面内容不白）。

**补丁（2026-10-24 下午）**：从首页 Banner 点进去时，如果首页数据还没到，
`HomePage._playlists` 仍是演示数据，于是拿演示 id（101 起）去查歌单详情，
得到一个解析失败 + 一条红条。现在 `open_playlist()` 里先判断 `is_demo_playlist()`，
命中就直接用本地数据渲染，**不发请求也不报错**；真实 id 失败仍然提示。
截图 `shots/23_demo_playlist.png`。

---

### P8 · 歌手页 / 专辑页 ✅

**实测（2026-10-24）**
- `/api/v1/artist/{id}` → `{artist, hotSongs[50], more}`；`artist.picUrl` 是头像，
  `musicSize` / `albumSize` 是作品数量，`alias` 是别名（「Jay Chou / 周董」）。
- `/api/v1/album/{id}` → `{album, songs[]}`；`publishTime` 是毫秒时间戳，
  `artists` 是合作歌手，`description` 可能是 `null`。
- `/api/v1/artist/detail` 与 `/api/v1/album/detail/{id}` 都返回 400，**只有上面两条路径可用**。

**做法：不新建页面，复用歌单页**
`PlaylistPage.set_playlist()` 增加 `subtitle` / `chip` / `round_cover` 三个可选参数：
- 歌手：`chip="歌手"`、圆形头像、副标题「歌手 · 50 首热门 · 作品 582 首」；
- 专辑：`chip="专辑"`、方形封面、副标题「周杰伦 / 方文山 · 2002 年 · 13 首」；
- 歌单：三个参数都不传，行为和以前完全一致。

**接线**
- 新增 `api/models/{artist,album}.py`、`api/modules/{artist,album}.py`、
  `catalog.to_playlist_from_{artist,album}()`；
- `SearchPage` 新增 `artistActivated(int)` / `albumActivated(int)`（原来点卡片只是播第一首）；
- `MainWindow.open_artist()` / `open_album()`，失败仍走顶部错误条。

**坑**：改 `main_window.py` 时把 `_on_playlist_error` 的一行 `_show_error` 误留在了
`_apply_album` 里，导致回调抛 `NameError`。PyQt6 对槽函数里的未捕获异常会直接
`qFatal` 结束进程——**没有 traceback、退出码 127**，看起来像段错误。排查方式：
先把回调逻辑拆出来在主线程序列化调用一遍，异常就现形了。

**验收**：截图 `shots/24_artist_page.png`（周杰伦 · 50 首）、`25_album_page.png`（Partners 拍档 · 13 首）。

---

## 3. 关键设计决策

| 议题 | 决定 | 理由 |
|---|---|---|
| 封面图 | **真实图优先**（`services/covers.py` 下载 + 磁盘缓存），月牙只做空态 | 已落地：`CoverArt` / `CoverCard` / `VinylDisc` 都收 `cover_url` |
| 歌词 | 官方 `/api/song/lyric` 的 `lrc.lyric`，解析成本地 `(ms, text)` | 与 `LyricView` 现有入参完全一致 |
| 分页 | 搜索只做「首屏 30 条」，滚动加载还没做 | 目前够用；要做时只需给 `SearchPage` 加「加载更多」 |
| 播放失败 | `available=False` 但有 `fallback` → 播试听并标注；都没有 → 跳过并提示 | 与 `ResolveOutcome` 语义一致 |
| 缓存 | 列表 5min / 详情 10min / 直链 `min(expi-120, 900)` | 已在 store 层实现，页面不用管 |
| 线程 | 所有请求走 `QtAsyncBridge`，回调在主线程 | 避免 UI 线程阻塞 |

---

## 4. 涉及文件清单（按阶段）

```
P0 新增  services/catalog.py  services/lyrics.py            ✅
   新增  api/modules/{playlist,lyric,personalized}.py       ✅
   新增  api/models/{playlist,lyric,personalized}.py        ✅
   改动  data.py（Playlist + desc 字段）                     ✅
   测试  tests/{test_catalog,test_lyrics,test_modules_ui}.py ✅
P1 改动  pages/home.py（+2 个方法，抽 2 个私有方法）         ✅
   改动  main_window.py（异步拉取 + 桥接 + 退出清理）          ✅
P2 改动  main_window.py（open_playlist 异步化）               ✅
   改动  pages/playlist.py（简介用真实 desc）                 ✅
P3 改动  pages/search.py（set_results + resultsRequested + 防抖）   ✅
   改动  main_window.py（320ms 防抖 + 按 Tab 懒加载）              ✅
   新增  api/models/search.py（ArtistHit / AlbumHit / PlaylistHit）✅
   改动  api/modules/search.py（SearchKind + 四类函数）            ✅
   测试  test_search.py / test_catalog.py 补 4 类用例              ✅
P3.5 新增 services/covers.py（异步下载 + 磁盘缓存 + ready 信号）      ✅
     改动 widgets/{cover,vinyl}.py（cover_url + 空态回落）           ✅
     改动 data.py（Track/Playlist + cover_url）  services/catalog.py  ✅
     测试 tests/test_covers.py（4 项）                                ✅
P4 改动  pages/now_playing.py（set_lyrics）                            ✅
     改动  main_window.py（切歌拉歌词）  widgets/lyrics.py（幽灵行）  ✅
P5a 新增 services/secret_store.py（DPAPI / AES-GCM）                      ✅
     新增 services/login_browser.py（QWebEngineView + cookie 抓取）         ✅
     新增 services/account.py（白名单落盘 / 恢复 / 退出）                    ✅
     改动 pages/settings.py（+账号页）  main_window.py（登录态联动）          ✅
     改动 main.py（AA_ShareOpenGLContexts + 代理桥接）                       ✅
     测试 tests/{test_secret_store,test_account}.py + tools/smoke_login.py   ✅
P5b 改动 widgets/sidebar.py（+set_my_playlists）  main_window.py（登录后重拉）  ✅
     新增 api/models/user.py（UserPlaylist）+ modules/user.get_user_playlists     ✅
     改动 services/catalog.py（split_user_playlists）  api/models/playlist.py（容忍 null）✅
     测试 tests/test_catalog.py 补 3 项  tools/verify_account_ui.py                 ✅
P6.5 改动 core/player.py（双引擎 + 直链注入 + duration_ms）  data.py（Track.remote）  ✅
     改动 services/catalog.py（标记 remote）  services/download/store.py（同上）        ✅
     改动 widgets/player_bar.py（seek 用真实时长）  main_window.py（解析注入 + 错误条） ✅
     测试 tests/test_player_logic.py（15 项）  tools/verify_playback.py                  ✅
P6 新增 services/paths.py  services/settings_store.py  services/error_text.py       ✅
   新增 services/download/{naming,store,service,notice}.py                         ✅
   新增 widgets/notice.py（InlineBanner）  NOTICE.txt                              ✅
   改动 data.py（DownloadTask 扩字段、删演示任务）  pages/download.py（订阅服务）   ✅
   改动 pages/settings.py（下载三控件 + 音质下拉）  pages/playlist.py（下载带曲目） ✅
   测试 tests/test_download_{naming,store,service}.py + test_settings_store.py      ✅
P7 改动  pages/settings.py（音质下拉接 QualityLevel）  main_window.py（错误提示条）
```

> 每个阶段都只「加方法 / 换内部实现」，不改布局与样式表。

---

## 5. 决策记录（2026-10-24 已确认）

| # | 议题 | 决定 |
|---|---|---|
| 1 | 登录方式 | **开浏览器登录 → 抓 Cookie → 加密存本地**（已落地：内嵌 Chromium + DPAPI，不实现 weapi） |
| 2 | 播放内核 | **先保留虚拟时钟**，数据全部接完再换 `QMediaPlayer` |
| 3 | 下载范围 | **统统允许下载**；界面与文档标注「仅供个人学术研究，严禁商业使用与传播」 |
| 4 | 封面 | **真实封面优先，月牙只做空态**（未加载/失败/无图时回落） |

---

## 6. 风险与依赖

1. **浏览器登录的依赖**：内嵌登录要 `PyQt6-WebEngine`（约 150MB，需 `pip install PyQt6-WebEngine`）。
   装不上就退化为「粘贴 Cookie」输入框，功能不丢。
2. **接口随时可能变**：所有模块都过 pydantic 校验，变了会报 `PARSE_ERROR` 而不是脏数据；
   `tests/fixtures` 里存的是真实回包，字段漂移会先让单测红。
3. **UI 与数据解耦的边界**：页面只认 `Track`/`Playlist`，一旦发现某页需要新字段
   （比如专辑页要发行时间），先在 `data.py` 加字段、再在 `catalog` 里映射，不要在页面里读接口模型。
4. **Cookie 的安全边界**：加密文件只存 `MUSIC_U` / `__csrf` / `NMTID` 三个键，
   主密钥走 DPAPI；日志里这些键一律打码（`core/logging.py` 已实现）。

---

## 7. 建议的执行顺序

P0–P7 全部完成，界面上的每一块都是真数据。剩下的是「已知缺口」：歌手页 / 专辑页、
喜欢与收藏的写操作、搜索分页——它们都需要先实测新接口，不属于收尾范围。
P5、P6、P6.5 都已完成，界面上的每一块都是真数据了。
