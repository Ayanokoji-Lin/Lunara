"""音质档位与降级链。

降级顺序写死在这里（jymaster → hires → lossless → exhigh → higher → standard），
Provider 只负责「这一档能不能给我 url」，不关心顺序。
"""
from __future__ import annotations

from .types import QualityLevel

#: 从高到低。编排层按 ``chain_from(preferred)`` 取子串，不会越过用户偏好。
DEGRADE_CHAIN: tuple[QualityLevel, ...] = (
    QualityLevel.JYMASTER,
    QualityLevel.HIRES,
    QualityLevel.LOSSLESS,
    QualityLevel.EXHIGH,
    QualityLevel.HIGHER,
    QualityLevel.STANDARD,
)


def chain_from(preferred: QualityLevel) -> tuple[QualityLevel, ...]:
    """从偏好档开始往下，到 standard 结束。

    >>> [level.value for level in chain_from(QualityLevel.LOSSLESS)]
    ['lossless', 'exhigh', 'higher', 'standard']
    """
    start = DEGRADE_CHAIN.index(preferred)
    return DEGRADE_CHAIN[start:]


# --------------------------------------------------------------------------- #
# GD Studio 的档位映射
#
# 实测（2026-10-24）：GD 只有 4 个 br 档位，且 br >= 700 都返回同一个无损文件
# （请求 999 / 1999 / 740 都回 br=797）。所以 jymaster/hires/lossless 要合并成一档，
# 否则同一份文件会被请求三次。
# --------------------------------------------------------------------------- #

#: 我方档位 → GD 的 ``br`` 参数
GD_BR_FOR_LEVEL: dict[QualityLevel, int] = {
    QualityLevel.JYMASTER: 999,
    QualityLevel.HIRES: 999,
    QualityLevel.LOSSLESS: 999,
    QualityLevel.EXHIGH: 320,
    QualityLevel.HIGHER: 192,
    QualityLevel.STANDARD: 128,
}

#: 反推用阈值：实际回包 br 落在哪个区间就算哪档
_BR_FLOORS: tuple[tuple[int, QualityLevel], ...] = (
    (700, QualityLevel.LOSSLESS),
    (300, QualityLevel.EXHIGH),
    (180, QualityLevel.HIGHER),
)


def gd_br_for(level: QualityLevel) -> int:
    """档位 → GD ``br`` 参数。"""
    return GD_BR_FOR_LEVEL[level]


def level_from_gd_br(br: int) -> QualityLevel:
    """实际码率 → 档位。``br=0``（失败）按 standard 记。"""
    for floor, level in _BR_FLOORS:
        if br >= floor:
            return level
    return QualityLevel.STANDARD


def gd_levels_from(preferred: QualityLevel) -> tuple[QualityLevel, ...]:
    """降级链去掉「映射到同一个 br」的重复档。

    >>> [level.value for level in gd_levels_from(QualityLevel.JYMASTER)]
    ['jymaster', 'exhigh', 'higher', 'standard']
    """
    seen: set[int] = set()
    levels: list[QualityLevel] = []
    for level in chain_from(preferred):
        br = GD_BR_FOR_LEVEL[level]
        if br in seen:
            continue
        seen.add(br)
        levels.append(level)
    return tuple(levels)
