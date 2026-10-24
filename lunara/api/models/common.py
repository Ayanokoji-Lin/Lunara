"""跨模块共用的最小领域模型。

字段名一律用 Python 风格，上游的短字段（dt / al / ar / alia）用 alias 映射。
所有模型都 ``extra="ignore"``：上游字段经常增删，多出来的不当作错误。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    """项目内所有上游模型的基类。"""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)

    @field_validator("*", mode="before")
    @classmethod
    def _null_strings_to_empty(cls, value, info):
        """上游经常把 ``picUrl`` / ``nickname`` 之类给成 null。

        以前一个 null 就让整包校验失败——搜「Alan Walker」直接零结果，因为
        某几个歌手的 picUrl 是 null。这里把「字符串字段收到 None」统一降级成空串。
        """
        if value is None:
            field = cls.model_fields.get(info.field_name)
            annotation = getattr(field, "annotation", None)
            args = getattr(annotation, "__args__", ())
            if annotation is str or str in args:
                return ""
        return value


class ArtistRef(StrictModel):
    id: int
    name: str


class AlbumRef(StrictModel):
    id: int
    name: str
    pic_url: str = Field(default="", alias="picUrl")


class Privilege(StrictModel):
    """播放权限位。``fee`` 1/4 表示会员专享，``st`` < 0 表示下架。"""

    id: int = 0
    fee: int = 0
    payed: int = 0
    st: int = 0
    pl: int = 0
    dl: int = 0
    max_br: int = Field(default=0, alias="maxbr")
    max_br_level: str = Field(default="", alias="maxBrLevel")
    flag: int = 0
