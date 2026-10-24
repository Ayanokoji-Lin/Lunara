"""播客（电台）接口。

实测（2026-10-24）：``/api/personalized/djprogram`` 返回 6 条推荐单集；
``/api/dj/program`` 是 404，``/api/dj/program/byradio`` 可用但需要真正的电台 id。
"""
from __future__ import annotations

from ..client import ApiClient
from ..endpoints import DJ_RECOMMEND
from ..models.dj import DjRecommend


async def get_recommend_programs(client: ApiClient, *, use_cache: bool = True) -> DjRecommend:
    """首页级的推荐单集（上游一次给 6 条，不支持分页）。"""
    return await client.call(
        DJ_RECOMMEND,
        {},
        model=DjRecommend,
        unwrap="none",
        cache="list" if use_cache else "none",
    )
