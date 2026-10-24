# 剩余功能计划（P9–P13）

> P0–P8 已完成。这里列剩下的五块，按「能验证的先后」排序，每块独立提交。

| # | 内容 | 状态 | 关键风险 |
|---|---|---|---|
| P9 | 喜欢 / 取消喜欢（同步到账号） | ✅ 完成 | 写接口参数已实测 |
| P10 | 搜索分页（加载更多） | ✅ 完成 | 低 |
| P11 | 本地播放（下载完的文件直接放） | ✅ 完成 | 低 |
| P12 | 亮色主题 | ✅ 完成（重启生效） | 已修轮播文字与播放页遮罩 |
| P13 | 打包（PyInstaller） | ✅ 完成（583 MB） | 体积主要来自 QtWebEngine |

## P9 · 喜欢

**实测（2026-10-24）**：`/api/song/like` 参数是 `trackId` + `like`（`"true"`/`"false"`）+ `time`，
返回 `{code:200, playlistId}`。之前用 `uid` 传参才一直 400。

- `api/modules/song.like_song(client, track_id, liked) -> int`
- `Player.set_liked(track_id, liked)`（不发信号，供失败回滚）
- `MainWindow` 监听 `likeChanged` → 异步同步；失败回滚 + 顶部提示
- 未登录时只改本地，不发请求

**验收**：真机点星标两次（喜欢 / 取消），`/api/song/like` 均 200，界面无错误条。
单测 3 项覆盖参数拼装与「写操作不走缓存」。
**已知取舍**：启动时不会拉取「已喜欢」的 id 列表，所以已喜欢的歌初始显示为未点亮；
点一下是幂等的（服务端按 `like=true` 再确认一次）。

## P10 · 搜索分页

- `SearchPage` 单曲列表底部加「加载更多」，`offset` 递增，去重追加
- 关键词变化时重置 offset

**验收**：搜「周杰伦」→ 30 首；点「加载更多」→ 60 首，唯一 id 也是 60（无重复）。

## P11 · 本地播放

- `Player.play_file(track, path)`：`media.setSource(QUrl.fromLocalFile(path))`，走 media 引擎
- 下载页「已完成」行加播放按钮；播放栏/歌词照常

**验收**：`play_file` 直接放本地 FLAC，position 3.7s / duration 320.4s 正常。
下载页「已完成」行新增播放按钮（与打开文件夹并排）。

## P12 · 亮色主题

- 设置页加「外观」切换（深空 / 月光白），`theme.apply(LIGHT)` + 全局重设 QSS + repolish
- 重点修：播放页背景遮罩、星光粒子在浅色下的可见度
- 封面/黑胶属于「唱片」语义，保持深色不做反转

**验收**：`shots/26_light_home.png`、`27_light_playlist.png`。切换写进设置，**重启生效**
（页面里不少颜色是构造时写进内联样式的，运行时热切换会留下旧色）。
已修两处不跟随主题的地方：轮播标题（底图固定深色，文字固定浅色）、播放页遮罩（改用 `bg_main`）。

## P13 · 打包

- `tools/build.py`（PyInstaller onedir）+ `Lunara.spec`
- 带上 qtawesome 字体与 QtWebEngine 资源
- 产物在 `dist/Lunara/`，不提交仓库

**验收**：`tools/build.py` 跑完产出 `dist/Lunara/Lunara.exe`（整个目录 583 MB，3 分 17 秒）；
直接启动 exe，进程正常起来并成功请求了登录态 / 首页 / 我的歌单，说明打包后的
资源与依赖是齐的（不只是弹个窗口）。

体积说明：QtWebEngine（登录窗口用的 Chromium）本身就占大头，加上 PyQt6 的 Qt6 DLL。
要压体积得砍掉内嵌浏览器登录，那等于砍功能，暂不处理。
