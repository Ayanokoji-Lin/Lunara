"""直链接口模型。

实测（2026-10-24，匿名）：
``/api/song/enhance/player/url/v1`` → ``data[0]`` 含
``url / br / size / code / expi(=1200 秒) / fee / level / type / freeTrialInfo / payed``。

两个关键事实：
1. ``level`` 是**实际下发**的档位，不是请求的档位。匿名请求 lossless/jymaster 也只回 standard。
2. 未登录时连免费歌都会带 ``freeTrialInfo``（试听 45 秒），所以 trial 判定就是它是否为 null。
"""
from __future__ import annotations

from pydantic import Field

from .common import StrictModel


class FreeTrialInfo(StrictModel):
    """试听片段区间（秒）。``start=0,end=45`` 即前 45 秒。"""

    start: int = 0
    end: int = 0

    @property
    def duration(self) -> int:
        return max(0, self.end - self.start)


class SongUrlItem(StrictModel):
    id: int
    url: str | None = None
    br: int = 0
    size: int = 0
    code: int = 200
    expi: int = 0
    fee: int = 0
    level: str = "standard"
    type: str | None = None
    payed: int = 0
    free_trial_info: FreeTrialInfo | None = Field(default=None, alias="freeTrialInfo")

    @property
    def trial(self) -> bool:
        return self.free_trial_info is not None

    @property
    def playable(self) -> bool:
        return bool(self.url) and self.code == 200


class SongUrlResponse(StrictModel):
    data: tuple[SongUrlItem, ...] = ()

    def first(self) -> SongUrlItem | None:
        return self.data[0] if self.data else None
