# Lunara 数据层 · 设计与验证记录

> 目标：给已完成 UI 的 Lunara 补上真实数据层，视觉与布局零改动。
> 实际做法是「新增 `lunara/api`、`services`、`store` + 给页面加数据注入口」，
> 页面里只加 `set_xxx()` 之类的方法，不重写界面。
> 技术栈：Python 3.13 / httpx（**全异步**）/ pydantic v2 / cryptography / pytest + pytest-asyncio。
> 界面接线与排期见 `docs/UI-INTEGRATION-PLAN.md`。

---

## 0. 架构决定

### 0.1 为什么没有独立的 BFF 进程

任务书里的 `server/` 是为浏览器端设计的（跨域、Cookie 不下发、密钥不进前端包）。
桌面端这三条都不成立，但「UI 不接触密钥」这个目标仍要守住，所以用**进程内分层**：

```
UI (lunara/pages, lunara/widgets)
   │  只 import lunara.api / lunara.services
   ▼
lunara/services/*           业务动作：直链决策、登录态、缓存编排
   ▼
lunara/api/modules/*        接口（search / song / user）
   ▼
lunara/api/client.py        异步请求层：重试 / 缓存 / 单飞 / 结构化日志
   ▼
lunara/api/core/*           密钥、eapi 组包、Cookie、日志（UI 永不 import）
   ▼
https://music.163.com/eapi/api/...
```

### 0.2 异步怎么落到 Qt 上

请求层是 `async def`，Qt 主线程没有事件循环，也不值得为几个请求引入 qasync：

```
Qt 主线程 ──submit(coro)──► 后台线程里的常驻 loop（async_bridge.BackgroundLoop）
    ▲                                   │
    └──── pyqtSignal 排队回主线程 ◄──────┘   （qt_bridge.QtAsyncBridge）
```

- `BackgroundLoop`：一条 daemon 线程 + `run_forever`，`submit()` 返回标准 `Future`。
- `QtAsyncBridge`：回调一定在主线程执行，可以放心碰控件。
- 脚本里用 `run_sync(coro)` 一把梭。

---

## 1. 已验证事实（2026-10-24 真机实测，全部可复现）

| 项 | 结论 | 证据 |
|---|---|---|
| eapi URL 形态 | `https://music.163.com/eapi` + `/api/...` | `/eapi/cloudsearch/pc` → `{"code":404,"message":"接口未找到"}`；`/eapi/api/cloudsearch/pc` → 200 |
| eapi 组包 | `md5("nobody{path}use{json}md5forencrypt")` 拼进 `{path}-36cd479b6b5-{json}-36cd479b6b5-{md5}`，AES-128-ECB（`e82ckenh8dichen8`，PKCS#7）→ 大写 hex | 固定向量送上游 → HTTP 200 / code 200 / songCount 276 |
| 响应形态 | 明文 JSON `{"code":200,...}`，未加密 | 同上 |
| 搜索 | `/api/cloudsearch/pc`，参数 `s,type,limit,offset,total` | `result.songs[*]` / `result.songCount` |
| 登录态 | `/api/nuser/account/get`，匿名 → `{"code":200,"account":null,"profile":null}` | 直接实测 |
| 会员字段 | `profile.vipType` 非 0 即会员（实测见过 11 / 110，具体档位含义未细分） | `/api/v1/user/detail/32953014` → `vipType=11`；登录账号 → `110` |
| 直链 | `/api/song/enhance/player/url/v1`，参数 `ids(JSON 串),level,encodeType` | `data[0].{url,br,expi,fee,level,freeTrialInfo}` |
| 直链有效期 | `expi=1200`（秒） | 匿名态实测 |
| 档位回显 | **`data[0].level` 是实际下发档位，不是请求档位**；匿名请求 lossless/jymaster 也只回 `standard / 128k` | 六档逐一实测 |
| 试听判定 | 未登录时**连免费歌**都带 `freeTrialInfo{start:0,end:45}`；`freeTrialInfo is not None` 即试听 | 匿名态实测 |
| 匿名 Cookie | `os=pc; appver=8.9.70; osver=...; channel=netease; __remember_me=true` 足够浏览 | 搜索/直链/登录态均 200 |
| 用户歌单 | `/api/user/playlist`，参数 `uid,limit,offset` → `playlist[]`（`specialType` / `subscribed`） | 登录态实测 12 个歌单 |
| 我喜欢的音乐 | 就是 `specialType=5` 的歌单，用歌单详情拿曲目 | 456 首实测 |
| 歌单字段可能为 null | `description` / `creator.nickname` 实测出现过 `null` | 私密歌单详情 |
| GD Studio 直链 | `GET https://music-api.gdstudio.xyz/api.php?types=url&source=netease&id=<id>&br=<128\|192\|320\|999>` → `{url,br,size,from}` | 347230 / 509781655 均返回可下载文件 |
| GD 失败形态 | HTTP 200 + `{"url":"","br":0,"size":0}`，不抛错 | `id=0` 实测 |
| GD 码率回显 | 请求 999 实际回 797 / 918；`br>=700` 视为无损 | 999/1999/740 三档实测同文件 |
| GD 完整性 | VIP 歌直链 HEAD 回 27.4MB `audio/mpeg`，**不是 45 秒试听** | `content-length=27401646` |

---

## 2. 目录（✅ = 已落地）

```
lunara/
├─ api/
│  ├─ client.py              异步请求层：eapi → 上游 → 校验 → 缓存 → 单飞 → 日志
│  ├─ endpoints.py           路径表（已实测 / UNVERIFIED 清单）
│  ├─ errors.py              ErrorCode / RETRY_LIMITS / ApiError
│  ├─ core/                  crypto（eapi 加解密）/ cookie / logging
│  ├─ models/                common / song / playlist / lyric / personalized /
│  │                         search / player_url / user
│  └─ modules/               search / playlist / lyric / song / user / personalized
├─ services/
│  ├─ catalog.py             接口模型 → Track / Playlist（UI 唯一数据入口）
│  ├─ covers.py              封面下载 + 磁盘缓存 + ready 信号
│  ├─ lyrics.py              LRC 解析
│  ├─ session.py             登录态 / 会员态（30s 快照）
│  ├─ account.py             登录 Cookie 白名单落盘 / 恢复 / 退出
│  ├─ secret_store.py        DPAPI / AES-256-GCM 加密存储
│  ├─ login_browser.py       内嵌浏览器登录 + Cookie 抓取
│  ├─ async_bridge.py        后台事件循环（BackgroundLoop / run_sync）
│  ├─ qt_bridge.py           协程结果回主线程（QtAsyncBridge）
│  └─ player_url/            types / quality / cache / service / providers{official,gdstudio}
└─ store/                    lru（TTLCache）/ inflight（AsyncSingleFlight）

tests/    145 项通过 + 5 项 live 冒烟；fixtures/ 存真实回包
tools/    probe_*（探针）、demo_*（数据层验收）、verify_*（UI 端到端）、smoke_login、shoot
```

---

## 3. 直链策略（官方 → GD Studio，已实现）

```
resolve(song_id, level)
  ① session：查 /api/nuser/account/get 判登录/会员（30s 快照；查失败降级匿名）
  ② official：/api/song/enhance/player/url/v1
        url 空 / 无版权 / fee∈{1,4} 且非会员 / 试听且非会员 → 不可用（试听留作兜底）
        完整可用 → 立即返回 {source:official, trial:false}
  ③ gdstudio：按 br 去重后的档位下降，单档最多 2 次（只重试 retryable）
  ④ 全失败 → available=false + fallback=官方试听 + error=URL_UNAVAILABLE
  ⑤ 成功即写缓存：ttl = min(expiresAt-now-120s, 900s)
  ⑥ 无论成败都产 trace{songId,level,triedProviders,finalSource,latencyMs,failReason}
```

### 3.1 GD Studio 档位映射（实测）

GD 只有 4 个 `br` 档，高码率三档映射到同一个文件，所以降级链要去重：

| 我方档位 | GD `br` | 实际回包 `br` | 判定档位 |
|---|---|---|---|
| jymaster | 999 | 797 / 918 | lossless |
| hires | 999 | 同上 | lossless |
| lossless | 999 | 同上 | lossless |
| exhigh | 320 | 320 | exhigh |
| higher | 192 | 192 | higher |
| standard | 128 | 128 | standard |

因此请求 `jymaster` 时实际只发 4 次请求（999 → 320 → 192 → 128），
并且返回的 `level` 如实写 `lossless`，不按请求档位吹成「超清母带」。

实测补充：匿名态必然走 ②→③（官方只给 45s 试听），GD 接通后匿名用户也能拿到
完整文件——`509781655` 实测 27.4MB / `audio/mpeg`。GD 关掉时 `fail_reason`
会写成 `VIP_REQUIRED+gdstudio:not_configured`，一眼看出缺哪块。

---

## 4. 错误码（`lunara/api/errors.py`）

| code | 触发 | 重试 | 后续 |
|---|---|---|---|
| `NETWORK` | 连接失败 / 超时 | 2（0.2→0.4s + 抖动） | 失败即抛 |
| `UPSTREAM_5XX` | HTTP 5xx / 业务 code≥500 | 1 | 仍失败则降级 |
| `AUTH_REQUIRED` | HTTP 401/403、业务 code 301 | 0 | 提示登录 |
| `VIP_REQUIRED` | fee∈{1,4} 且非会员 | 0 | 转 GD |
| `NO_COPYRIGHT` | 直链接口 code 404 / url 空 | 0 | 不可用 |
| `URL_UNAVAILABLE` | 全部 Provider 失败 | 0 | 回退试听 |
| `RATE_LIMITED` | HTTP 429 / code -460 | 0 | 告警 + 冷却 |
| `PARSE_ERROR` | 非 JSON / 模型不匹配 / 其它 4xx | 0 | 记脱敏原始响应 |

---

## 5. 阶段进度

| 阶段 | 状态 | 验收 |
|---|---|---|
| ① 计划与目录 | ✅ | 本文档 |
| ② crypto + 请求层 + 搜索跑通 | ✅ | 单测通过；`demo_search.py 周杰伦` 276 条真实结果 |
| ③ 直链策略 + 测试 | ✅ | 12 个决策场景 + 8 个 GD 用例全绿；`demo_player_url.py` 真机输出 trace |
| ④ 其余接口 | ✅ | 歌单详情 / 推荐 / 新歌 / 歌词 / 搜索四类 / 用户歌单 均已实测并接入 |
| ⑤ 文档 | ✅ | 本文档 + `UI-INTEGRATION-PLAN.md` + `ARCHITECTURE.md`（不再单独写 README-api） |

> 数据层到此收口。界面接线的进度见 **`docs/UI-INTEGRATION-PLAN.md`**。

---

## 6. 待补 / 待确认

**待确认**
1. 音质偏好还没接：设置页那 4 档下拉目前只是 UI，没有驱动 `QualityLevel`
   （4 档正好对应 standard / higher / exhigh / lossless，接起来很轻）。
2. GD Studio 的其它 `types`（`search` / `lyric` / `pic` / `playlist`）**不接**——
   歌词与封面走官方已经够用，多一条链路只多一处风险。

**待实测（`endpoints.UNVERIFIED`）**
3. 专辑 / 歌手 / MV / 评论 / 用户详情。搜索卡片点进去目前只是占位。
4. 评论分页游标语义（`before` / `time` / `offset` 谁是主键）。
5. 匿名 Cookie 的官方换取接口（`/api/register/anonimous`）——目前固定匿名串可用，暂不需要。

**已确认不可用**
6. `/api/song/like` 在 eapi 下恒 `code=400`（uid 传 int / str 都一样，疑似仅 weapi 支持）。
   「我喜欢的音乐」改走 `specialType=5` 的歌单，详情接口照常返回全部曲目。

**已知取舍**
7. 「逐级重试 ≤2」按「单档最多 2 次尝试」实现（`max_attempts=2`），可配。
8. 登录态 30 秒快照：登录/退出后最多 30 秒内可能读到旧值，`SessionService.invalidate()` 可立即清。
9. GD 不给 `expi`，直链缓存走默认 300s；若实测发现链接更短命，把 `UrlCache(default_ttl=...)` 调小即可。
10. `playlist.description` / `creator.nickname` 可能是 `null`，模型按 `str | None` 容忍。
