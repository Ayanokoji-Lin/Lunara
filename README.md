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

首次运行会通过 qtawesome 加载 FontAwesome 图标字体，无需任何外部图片素材
（所有封面都是 QPainter 程序化生成的）。

## 已实现

- 无边框窗口：悬浮阴影、`startSystemMove` 拖动、双击标题栏最大化、右下角缩放
- 侧边栏：弯月 Logo、主导航、我的音乐、可折叠歌单组、3px 主色指示条
- 首页：Banner 淡入淡出轮播、5 列推荐歌单网格（播放量胶囊 / 两行截断标题）
- 歌单详情：180px 封面 + 柔光投影、播放全部、QTableView 歌曲表
- 播放页三种模式：唱片+歌词 / 纯歌词 / 纯封面（星光粒子），高斯模糊背景
- 搜索页：单曲列表 + 歌手 / 专辑 / 歌单网格
- 本地下载：任务总览、逐条进度（下载中流光 / 暂停 / 完成 / 失败）、暂停·重试·删除、分类筛选、批量控制
- 设置页：左分类导航 + 胶囊开关 + 下拉框
- 播放栏：旋转小唱片、进度条点击跳转、音量、播放模式、播放队列

## 数据层（进行中）

首页（推荐歌单 / 新歌速递）、歌单详情、搜索四类（单曲 / 歌手 / 专辑 / 歌单）、
歌词与封面已接真实数据；登录 / 下载仍走演示数据。

封面规则：有真实图就显示，拿不到（未加载完 / 失败 / 接口没给）才回落到程序化月牙封面——
所以列表里看到的月牙就是「还在加载」的空态。

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
.venv/Scripts/python.exe -m pytest              # 125 项，全打桩不联网
LUNARA_LIVE=1 .venv/Scripts/python.exe -m pytest tests/test_live.py   # 真上游冒烟
.venv/Scripts/python.exe tools/demo_search.py 周杰伦
.venv/Scripts/python.exe tools/demo_player_url.py 347230 lossless
.venv/Scripts/python.exe tools/verify_ui_live.py                      # 首页/歌单端到端 + 截图
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

## 说明

当前音频层是「虚拟时钟」（`lunara/core/player.py`），用于先把界面跑通；
接入真实播放只需把时钟换成 `QMediaPlayer`，UI 侧信号无需改动。

下载页同理：进度由 `QTimer` 模拟推进，换成 `QNetworkAccessManager` / aria2
（断点续传状态落 SQLite）后，`DownloadRow` 与页面逻辑不用改。

界面截图见 `shots/`，架构与工程细节见 `docs/ARCHITECTURE.md`。

## 版本管理

- 分支只有 `main`，一个阶段一个提交，消息前缀用 `feat / fix / test / docs / chore`。
- 入库：源码、`tests/fixtures`（真实回包，字段漂移时单测会先红）、`tools`、`docs`、`shots`。
- 不入库：`.venv/`、`__pycache__/`、`.pytest_cache/`、`.secrets/`、`*.enc`、`covers/`、`.workbuddy-ai/`。
- **登录态与主密钥永不入库**（P5 的 `session.enc` 已在 `.gitignore` 里）。
- 回滚点：`git tag` 里的 `baseline-*` 标记了每个可验收的状态。
