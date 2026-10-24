"""下载声明文案与落盘。

用户确认过：下载**统统允许**，但界面与文档都要标注「仅供个人学术研究，
严禁任何形式的商业使用和传播」。这里把文案集中一处，UI 与 NOTICE.txt 共用。
"""
from __future__ import annotations

from pathlib import Path

NOTICE_TITLE = "仅供个人学习与研究"
NOTICE_TEXT = (
    "下载内容仅供个人学习、研究使用；音乐版权归网易云音乐及版权方所有。"
    "严禁任何形式的商业使用、二次分发或批量抓取，请于 24 小时内自行删除。"
)

#: NOTICE.txt 的版本标记（用于判断是否需要重写）
NOTICE_MARKER = "# Lunara 下载声明 v1"

NOTICE_FILE_BODY = f"""{NOTICE_MARKER}

本目录下的音频文件由 Lunara 下载，仅供个人学习、研究使用。

- 音乐版权归网易云音乐及版权方所有，请支持正版。
- 严禁任何形式的商业使用、二次分发、批量抓取或公开传播。
- 建议在 24 小时内自行删除。

如不同意以上约定，请立即停止使用并删除本目录内容。
"""


def write_notice_file(directory: Path) -> bool:
    """把声明写到下载目录；已有同版本就跳过，不覆盖用户自己的文件。"""
    target = Path(directory) / "NOTICE.txt"
    try:
        if target.exists():
            head = target.read_text(encoding="utf-8", errors="ignore")[:64]
            if NOTICE_MARKER in head:
                return False
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(NOTICE_FILE_BODY, encoding="utf-8")
        return True
    except OSError:
        return False
