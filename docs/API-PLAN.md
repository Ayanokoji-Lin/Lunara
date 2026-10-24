# Lunari API 数据层 · 计划与进度（Python 版）

> 目标：给已完成 UI 的 Lunara 补上真实数据层，**不改任何 UI 代码**，只新增
> `lunara/api`、`lunara/services`、`lunara/store` 与 `tests`。
> 技术栈：Python 3.13 / httpx（**全异步**）/ pydantic v2 / cryptography / pytest + pytest-asyncio。

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
| 会员字段 | `profile.vipType`（0=非会员，11=音乐包/黑胶） | `/api/v1/user/detail/32953014` → `vipType=11` |
| 直链 | `/api/song/enhance/player/url/v1`，参数 `ids(JSON 串),level,encodeType` | `data[0].{url,br,expi,fee,level,freeTrialInfo}` |
| 直链有效期 | `expi=1200`（秒） | 匿名态实测 |
| 档位回显 | **`data[0].level` 是实际下发档位，不是请求档位**；匿名请求 lossless/jymaster 也只回 `standard / 128k` | 六档逐一实测 |
| 试听判定 | 未登录时**连免费歌**都带 `freeTrialInfo{start:0,end:45}`；`freeTrialInfo is not None` 即试听 | 匿名态实测 |
| 匿名 Cookie | `os=pc; appver=8.9.70; osver=...; channel=netease; __remember_me=true` 足够浏览 | 搜索/直链/登录态均 200 |
| GD Studio 直链 | `GET https://music-api.gdstudio.xyz/api.php?types=url&source=netease&id=<id>&br=<128\|192\|320\|999>` → `{url,br,size,from}` | 347230 / 509781655 均返回可下载文件 |
| GD 失败形态 | HTTP 200 + `{"url":"","br":0,"size":0}`，不抛错 | `id=0` 实测 |
| GD 码率回显 | 请求 999 实际回 797 / 918；`br>=700` 视为无损 | 999/1999/740 三档实测同文件 |
| GD 完整性 | VIP 歌直链 HEAD 回 27.4MB `audio/mpeg`，**不是 45 秒试听** | `content-length=27401646` |

---

## 2. 目录（✅ = 已落地）

```
lunara/
├─ api/
│  ├─ __init__.py            ✅ get_client() / aclose_client()
│  ├─ client.py              ✅ 异步请求层：eapi→上游→校验→缓存→单飞→日志
│  ├─ endpoints.py           ✅ 路径表（verified 标记 + UNVERIFIED 清单）
│  ├─ errors.py              ✅ ErrorCode / RETRY_LIMITS / ApiError
│  ├─ core/
│  │  ├─ crypto.py           ✅ eapi 加解密 + 固定向量
│  │  ├─ cookie.py           ✅ 匿名 Cookie / 登录注入
│  │  └─ logging.py          ✅ 结构化日志 + 脱敏
│  ├─ models/
│  │  ├─ common.py           ✅ StrictModel / ArtistRef / AlbumRef / Privilege
│  │  ├─ song.py             ✅ Song / SongSearchResult
│  │  ├─ player_url.py       ✅ SongUrlItem / SongUrlResponse / FreeTrialInfo
│  │  └─ user.py             ✅ Account / Profile / LoginStatus
│  └─ modules/
│     ├─ search.py           ✅ search_songs()
│     ├─ song.py             ✅ get_song_url() / get_song_urls()
│     └─ user.py             ✅ get_login_status()
├─ services/
│  ├─ async_bridge.py        ✅ BackgroundLoop / run_sync / shutdown
│  ├─ qt_bridge.py           ✅ QtAsyncBridge（回调回主线程）
│  ├─ session.py             ✅ SessionService（30s 快照，失败降级匿名）
│  └─ player_url/
│     ├─ types.py            ✅ QualityLevel / ResolvedUrl / ResolveTrace / ResolveOutcome / UrlProvider
│     ├─ quality.py          ✅ 降级链 chain_from()
│     ├─ cache.py            ✅ UrlCache（TTL 提前 2min，key=song:level:source）
│     ├─ service.py          ✅ PlayerUrlService 编排
│     └─ providers/
│        ├─ official.py      ✅ 官方音源（试听/会员判定）
│        ├─ gdstudio.py      ✅ GD Studio（br 档位、失败即无 url）
│        └─ schema.py        ✅ GdStudioUrlResponse（真实字段）
└─ store/
   ├─ lru.py                 ✅ TTLCache
   └─ inflight.py            ✅ AsyncSingleFlight

tests/                       85 项通过 + 5 项 live 冒烟
├─ test_crypto.py            ✅ 固定向量 + 明文结构 + padding
├─ test_client.py            ✅ 重试/错误映射/缓存/单飞/错误广播
├─ test_search.py            ✅ 参数拼装与入参校验
├─ test_session.py           ✅ 会员判定 / 快照 / 降级
├─ test_player_url.py        ✅ 12 个决策场景
├─ test_bridge.py            ✅ 后台 loop + Qt 回调线程
├─ test_gdstudio.py          ✅ schema / br 映射 / 错误映射 / 编排配合
├─ test_lru.py               ✅ TTL / 淘汰 / 统计
├─ test_live.py              ✅ 真上游（默认 skip）
└─ fixtures/cloudsearch_songs.json  ✅ 真实响应夹具

tools/
├─ demo_search.py            ✅ 搜索验收
├─ demo_player_url.py        ✅ 直链决策验收
└─ probe_*.py                ✅ 探针（路径/字段/档位实测证据）
```

---

## 3. 直链策略（已实现，GD 待接入）

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
| ④ 其余接口 | 🟡 拆到 `docs/UI-INTEGRATION-PLAN.md` 的 P0–P3 | 歌单详情/推荐/歌词/搜索四类已实测可用；剩余见新计划 |
| ⑤ 文档 | ⬜ | `README-api.md`（架构/错误码/音质映射/环境变量/新增 Provider 指引） |

> 数据层到此收口。后续「把界面接上真实数据」的排期见 **`docs/UI-INTEGRATION-PLAN.md`**。

---

## 6. 待补 / 待确认

**待确认**
1. 音质偏好从哪来：设置页现有选项要不要映射成 `QualityLevel`（standard/higher/exhigh/lossless/hires/jymaster）。
2. GD Studio 的其它 `types`（`search` / `lyric` / `pic` / `playlist`）要不要接——
   参考实现里有，但本项目歌词/封面已能走官方，接之前先定边界。

**待实测（已列进 `endpoints.UNVERIFIED`）**
3. 歌曲详情 `/api/v3/song/detail`、歌单 `/api/v6/playlist/detail`、专辑/歌手/MV/评论/用户详情。
4. 评论分页游标语义（`before` / `time` / `offset` 谁是主键）。
5. 匿名 Cookie 的官方换取接口（`/api/register/anonimous`）是否必需——目前固定匿名串可用。

**已知取舍**
6. 「逐级重试 ≤2」按「单档最多 2 次尝试」实现（`max_attempts=2`），可配。
7. 登录态 30 秒快照：登录/退出后最多 30 秒内可能读到旧值，`SessionService.invalidate()` 可立即清。
8. GD 不给 `expi`，直链缓存走默认 300s；若实测发现链接更短命，把 `UrlCache(default_ttl=...)` 调小即可。
