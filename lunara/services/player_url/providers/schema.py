"""GD Studio 响应 schema。

协议来源：隔壁 ``Cadenza-Public/cadenza/core/gdstudio.py`` 的实现 + 2026-10-24 实测复核。

    GET https://music-api.gdstudio.xyz/api.php
        ?types=url&source=netease&id=<song_id>&br=<128|192|320|999>
        → {"url": str, "br": int, "size": int, "from": str}

实测细节（与参考实现一致的部分 / 需要补充的部分）：

- 失败也是 HTTP 200，返回 ``{"url": "", "br": 0, "size": 0}``，所以「url 为空」必须当失败处理；
- ``br`` 是**实际码率**，不等于请求值：请求 999 实际回 797 / 918，所以档位要按区间反推；
- 没有 ``expi`` 字段，拿不到链接过期时间（缓存走默认 TTL，见 ``UrlCache``）。
"""
from __future__ import annotations

from pydantic import Field

from ....api.models.common import StrictModel


class GdStudioUrlResponse(StrictModel):
    """``types=url`` 的返回。"""

    url: str = ""
    br: int = 0
    size: int = 0
    from_: str = Field(default="", alias="from")

    @property
    def playable(self) -> bool:
        return bool(self.url.strip())


#: TODO: 阶段④ 若要用 GD 的 search/lyric/pic，在这里补对应模型；
#: 字段以 ``types=search|lyric|pic`` 的真实响应为准，不要按文档臆测。
