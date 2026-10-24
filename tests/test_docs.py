"""文档健康检查：标题不重复、代码块成对。

为什么值得写成测试：改文档时用脚本做替换，很容易把同一段插进去两次
（README 的主题 / 播放说明就重复过），肉眼看 diff 未必发现。
"""
from __future__ import annotations

import collections
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_headings_are_unique(path: Path) -> None:
    headings = [
        line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    ]
    duplicated = [h for h, count in collections.Counter(headings).items() if count > 1]

    assert not duplicated, f"{path.name} 有重复标题：{duplicated}"


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_code_fences_balanced(path: Path) -> None:
    fences = sum(
        1 for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("```")
    )

    assert fences % 2 == 0, f"{path.name} 的 ``` 不成对（{fences} 个）"


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_no_duplicated_paragraphs(path: Path) -> None:
    """相邻的 4 行完全重复，多半是替换脚本插了两遍。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    for i in range(len(lines) - 7):
        block = lines[i:i + 4]
        if not any(line.strip() for line in block):
            continue
        assert block != lines[i + 4:i + 8], f"{path.name} 第 {i + 1} 行起有重复段落"
