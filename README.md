# Lunara

> 深空、星轨、月光 —— 基于 PyQt6 的沉浸式音乐播放器界面。

底层信息架构参考网易云音乐 PC 端（侧边栏 / 顶栏 / 内容区 / 播放栏四模块），
视觉语言完全重写：深空黑 + 星夜紫 + 月光银，无 Mica、无 Win11 大圆角。

## 运行

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -r requirements.txt
python main.py
```

首次运行会通过 qtawesome 加载 FontAwesome 图标字体，不依赖任何图片素材文件：
封面优先用接口给的真实图（异步下载 + 磁盘缓存），拿不到才用 QPainter 生成的月牙封面兜底。

登录功能需要 `PyQt6-WebEngine`（已写进 `requirements.txt`）；没装时应用照常运行，
只是「登录」会退化成一句安装提示。

## 已实现

- 无边框窗口：悬浮阴影、`startSystemMove` 拖动、双击标题栏最大化、右下角缩放
- 侧边栏：弯月 Logo、主导航、我的音乐、可折叠歌单组、3px 主色指示条
- 首页：Banner 淡入淡出轮播、5 列推荐歌单网格（播放量胶囊 / 两行截断标题）
- 歌单详情：180px 封面 + 柔光投影、播放全部、QTableView 歌曲表
- 播放页三种模式：唱片+歌词 / 纯歌词 / 纯封面（星光粒子），高斯模糊背景
- 搜索页：单曲列表 + 歌手 / 专辑 / 歌单网格，四类都能点进详情
- 歌手页 / 专辑页：复用歌单页骨架，歌手用圆形头像 + 50 首热门，专辑给曲目与发行年
- 本地下载：任务总览、逐条进度、暂停·重试·删除、分类筛选、批量控制；
  真实流式下载 + Range 断点续传 + SQLite 任务表（重启自动续传）
- 设置页：左分类导航 + 胶囊开关 + 下拉框 + 账号页（登录 / 退出 / 会员态）
- 侧栏「我的歌单」：登录后换成真实歌单分组，「我喜欢的音乐」直达对应歌单
- 播放栏：旋转小唱片、进度条点击跳转、音量、播放模式、播放队列
- 真实播放：`QMediaPlayer` + 直链解析（官方 → GD 降级），进度/时长/seek 全走真实音频
- 喜欢：星标同步到账号（`/api/song/like`），失败自动回滚并提示
- 搜索分页：单曲列表「加载更多」，按 30 条一页追加、自动去重
- 本地播放：下载完成的文件可直接播（不联网、不走直链）
- 主题：深空 / 月光白两套，设置里切换，重启生效
- 真实播放：`QMediaPlayer` + 直链解析（官方 → GD 降级），进度/时长/seek 全走真实音频
- 喜欢：星标同步到账号（`/api/song/like`），失败自动回滚并提示
- 搜索分页：单曲列表「加载更多」，按 30 条一页追加、自动去重
- 本地播放：下载完成的文件可直接播（不联网、不走直链）
- 主题：深空 / 月光白两套，设置里切换，重启生效

## 数据层

首页（推荐歌单 / 新歌速递）、歌单详情、搜索四类（单曲 / 歌手 / 专辑 / 歌单）、
歌词、封面、下载都已接真实数据；账号登录可用，登录后侧栏会换成真实歌单与「我喜欢的音乐」。

登录方式：设置 → 账号 → 登录，会弹一个内嵌浏览器窗口，你在里面正常登录网易云，
登录成功后自动抓取 Cookie 并用 **Windows DPAPI** 加密存到
`%APPDATA%/Lunara/session.enc`；退出登录即删除该文件。
若登录窗口一片空白，多半是显卡上下文问题，用 `QT_OPENGL=software` 启动一次即可。

封面规则：有真实图就显示，拿不到（未加载完 / 失败 / 接口没给）才回落到程序化月牙封面——
所以列表里看到的月牙就是「还在加载」的空态。

演示歌单（`data.py` 里 id 101 起的那些）只在本地渲染，不会拿去请求接口；
首页数据还没到时点 Banner，看到的就是这份本地内容，不会冒出一条错误提示。

真实数据从网易云 eapi 走，`lunara/api/` 负责组包、重试、校验与缓存，
`lunara/services/` 负责直链决策、登录态与模型适配，`lunara/store/` 提供 TTL-LRU 与并发单飞。
请求层全异步，UI 不接触加密密钥，也不直接拼请求。

直链按「官方 → GD Studio」降级：官方只给 45 秒试听（或干脆不给）时，
自动转 GD Studio 取完整文件，并把实际码率如实标成档位。

| 环境变量 | 默认 | 作用 |
|---|---|---|
| `LUNARA_GDSTUDIO_BASE` | `https://music-api.gdstudio.xyz/api.php` | 换 GD 地址 |
| `LUNARA_GDSTUDIO_DISABLED` | 空 | 置 `1` 关掉降级源 |
| `LUNARA_MUSIC_U` | 空 | 注入登录 Cookie |

```python
# 业务侧（协程）
from lunara.api import ApiClient
from lunara.api.modules.search import search_songs
from lunara.services.player_url import PlayerUrlService, QualityLevel

async with ApiClient() as client:
    result = await search_songs(client, "周杰伦", limit=30)
    outcome = await PlayerUrlService(client).resolve(347230, QualityLevel.LOSSLESS)
```

Qt 里不要自己 `await`，用桥接把协程丢到后台循环，回调回主线程：

```python
from lunara.services.qt_bridge import QtAsyncBridge

self._bridge = QtAsyncBridge(self)
self._bridge.submit(search_songs(client, text),
                    on_success=self._show_results,
                    on_error=self._show_error)
```

自检：

```bash
.venv/Scripts/python.exe -m pytest              # 145 项，全打桩不联网
LUNARA_LIVE=1 .venv/Scripts/python.exe -m pytest tests/test_live.py   # 真上游冒烟
.venv/Scripts/python.exe tools/demo_search.py 周杰伦
.venv/Scripts/python.exe tools/demo_player_url.py 347230 lossless
.venv/Scripts/python.exe tools/verify_ui_live.py                      # 首页/歌单端到端 + 截图
.venv/Scripts/python.exe tools/smoke_login.py                         # 登录窗口能否加载
.venv/Scripts/python.exe tools/verify_account_ui.py                   # 登录态：我的歌单 + 喜欢（需先登录）
.venv/Scripts/python.exe tools/verify_download.py                     # 真实下载（会写文件）
.venv/Scripts/python.exe tools/verify_playback.py                     # 真实播放（会出声）
.venv/Scripts/python.exe tools/verify_download.py                     # 真实下载（会写文件）
.venv/Scripts/python.exe tools/verify_playback.py                     # 真实播放（会出声）
```

分层、错误码、已验证的上游事实见 `docs/API-PLAN.md`，
UI 接真数据的排期与进度见 `docs/UI-INTEGRATION-PLAN.md`。

## 快捷键

| 按键 | 功能 |
|---|---|
| `Space` | 播放 / 暂停（输入框内不生效） |
| `Ctrl + ← / →` | 上一首 / 下一首 |
| `Ctrl + ↑ / ↓` | 音量 ±5 |
| `Esc` | 返回上一页 |

## 下载说明

**下载内容仅供个人学习、研究使用；音乐版权归网易云音乐及版权方所有。**
严禁任何形式的商业使用、二次分发或批量抓取。首次进入下载页会提示一次，
同时把同样的声明写进下载目录的 `NOTICE.txt`。

- 官方直链拿不到完整文件时（未登录 / 非会员），会自动走 GD Studio 取完整音频；
  两边都只有 45 秒试听时，任务会失败并说明原因，不会把试听片段存成整首。
- 暂停、退出应用、断网都会保留 `.part` 文件，恢复后从断点继续。
- 删除任务只删任务与 `.part`，已经下完的文件不会被动。

## 下载说明

**下载内容仅供个人学习、研究使用；音乐版权归网易云音乐及版权方所有。**
严禁任何形式的商业使用、二次分发或批量抓取。首次进入下载页会提示一次，
同时把同样的声明写进下载目录的 `NOTICE.txt`。

- 官方直链拿不到完整文件时（未登录 / 非会员），会自动走 GD Studio 取完整音频；
  两边都只有 45 秒试听时，任务会失败并说明原因，不会把试听片段存成整首。
- 暂停、退出应用、断网都会保留 `.part` 文件，恢复后从断点继续。
- 删除任务只删任务与 `.part`，已经下完的文件不会被动。

## 主题

设置 → 播放 → 外观主题：`深空`（默认）/ `月光白`。切换会写进
`%APPDATA%/Lunara/settings.json`，**重启应用后生效**——页面里不少颜色是在构造时
写进内联样式的，运行时热切换会留下旧色。

轮播图与封面属于「画作」，不跟随主题：底图始终是深色，标题固定用浅色。

## 播放说明

- 点播放时先解析直链，再交给 `QMediaPlayer`；解析是异步的，切歌后迟到的结果会被丢弃
  （内部用单调递增的 `seq` 判断），所以连续快速切歌不会串台。
- 进度条与歌词都用**真实时长**，和接口给的 `duration` 差几秒是正常的（编码差异）。
- 未登录/非会员遇到 VIP 歌：官方只给 45 秒，会自动转 GD 拿完整文件；
  两边都拿不到时顶部提示「只提供 45 秒试听片段」，不会假装在放整首。

## 主题

设置 → 播放 → 外观主题：`深空`（默认）/ `月光白`。切换会写进
`%APPDATA%/Lunara/settings.json`，**重启应用后生效**——页面里不少颜色是在构造时
写进内联样式的，运行时热切换会留下旧色。

轮播图与封面属于「画作」，不跟随主题：底图始终是深色，标题固定用浅色。

## 播放说明

- 点播放时先解析直链，再交给 `QMediaPlayer`；解析是异步的，切歌后迟到的结果会被丢弃
  （内部用单调递增的 `seq` 判断），所以连续快速切歌不会串台。
- 进度条与歌词都用**真实时长**，和接口给的 `duration` 差几秒是正常的（编码差异）。
- 未登录/非会员遇到 VIP 歌：官方只给 45 秒，会自动转 GD 拿完整文件；
  两边都拿不到时顶部提示「只提供 45 秒试听片段」，不会假装在放整首。

## 说明

播放和下载都已经是真的了。音频走 `QMediaPlayer`，直链由 `services/player_url`
解析（官方拿不到完整文件时降级 GD Studio）；没有音频设备或播演示曲目时自动退回
虚拟时钟，界面表现一致。

下载：任务表在 `%APPDATA%/Lunara/tasks.db`，文件落到设置里的下载目录
（默认 `D://Music//Lunara`），暂停/退出后重开自动续传。设置 → 下载可以改目录与并发数。

启动方式除了 `python main.py`，桌面上还有一个 `Lunara.bat`（用系统 Python，
缺库会自动装）。

界面截图见 `shots/`，架构与工程细节见 `docs/ARCHITECTURE.md`。

## 已知缺口

- **收藏歌单**：`/api/playlist/subscribe` 在 eapi 下恒返回 405「操作过于频繁」，暂不可用。
- **已喜欢的歌**：启动时不拉「我喜欢的音乐」的 id 列表，所以已喜欢的歌初始是未点亮状态；
  再点一次是幂等的（服务端按 `like=true` 再确认）。
- **本地曲库扫描**：现在只能播「下载页里已完成的文件」，还没有扫描任意目录、读标签（`mutagen`）。

## 打包

```bash
.venv/Scripts/python.exe tools/build.py      # PyInstaller onedir
dist/Lunara/Lunara.exe
```

产物在 `dist/Lunara/`（约 583 MB，主要是 QtWebEngine 的 Chromium），不入库。
想更小可以改成 `--onedir` + 手动排除未用的 Qt 模块，或者去掉内嵌登录。

## 打包

```bash
.venv/Scripts/python.exe tools/build.py      # PyInstaller onedir
dist/Lunara/Lunara.exe
```

产物在 `dist/Lunara/`（约 583 MB，主要是 QtWebEngine 的 Chromium），不入库。
想更小可以改成 `--onedir` + 手动排除未用的 Qt 模块，或者去掉内嵌登录。

## 版本管理

- 分支只有 `main`，一个阶段一个提交，消息前缀用 `feat / fix / test / docs / chore`。
- 入库：源码、`tests/fixtures`（真实回包，字段漂移时单测会先红）、`tools`、`docs`、`shots`。
- 不入库：`.venv/`、`__pycache__/`、`.pytest_cache/`、`.secrets/`、`*.enc`、`covers/`、`.workbuddy-ai/`。
- **登录态与主密钥永不入库**（P5 的 `session.enc` 已在 `.gitignore` 里）。
- 回滚点：`git tag` 里的 `baseline-*` 标记了每个可验收的状态。
