"""Lunara · 演示数据（曲库 / 歌单 / 歌词）

真实项目里这一层应替换为 SQLite + 本地文件扫描（mutagen 读标签），
UI 层只依赖这里的数据类，替换数据源不会影响界面代码。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Track:
    id: int
    title: str
    artist: str
    album: str
    duration: int          # 秒
    hue: int               # 程序化封面的色相
    liked: bool = False
    cover_url: str = ""    # 真实封面；空或加载失败时回落到月牙空态

    @property
    def seed(self) -> int:
        return self.id

    @property
    def duration_ms(self) -> int:
        return self.duration * 1000

    @property
    def duration_text(self) -> str:
        return f"{self.duration // 60:02d}:{self.duration % 60:02d}"


@dataclass(slots=True)
class DownloadTask:
    """下载任务（演示用；真实实现应持久化到 SQLite 并断点续传）。"""
    track: Track
    size_mb: float
    progress: float = 0.0          # 0..1
    speed: float = 0.0             # MB/s
    state: str = "downloading"     # downloading / paused / done / failed
    error: str = ""

    @property
    def done_mb(self) -> float:
        return self.size_mb * self.progress

    @property
    def percent(self) -> int:
        return int(round(self.progress * 100))


@dataclass(slots=True)
class Playlist:
    id: int
    title: str
    author: str
    plays: int
    hue: int
    tag: str = ""
    desc: str = ""                 # 真实简介（接口给的那段）；空则用默认文案
    cover_url: str = ""            # 真实封面；空或加载失败时回落到月牙空态
    tracks: list[Track] = field(default_factory=list)

    @property
    def plays_text(self) -> str:
        if self.plays >= 100_000_000:
            return f"{self.plays / 100_000_000:.0f}亿"
        if self.plays >= 10_000:
            return f"{self.plays / 10_000:.0f}万"
        return str(self.plays)


TRACKS: list[Track] = [
    Track(1, "月海拾音", "Lunara", "深空电台", 254, 258),
    Track(2, "星轨列车", "夜航员", "Orbit", 231, 214),
    Track(3, "潮汐与银线", "沐眠", "月光白", 288, 196),
    Track(4, "凌晨四点的雾", "林间有风", "Ambient No.4", 306, 280),
    Track(5, "环形山以南", "Silent Crater", "Mare", 197, 268),
    Track(6, "北极星睡着了", "折光", "Polaris", 245, 244),
    Track(7, "在银河尽头等你", "Lunara", "深空电台", 272, 292),
    Track(8, "月相不全", "陈默", "残缺的美", 219, 322),
    Track(9, "云层之上", "Above", "Stratus", 263, 210),
    Track(10, "碎星落进咖啡里", "小满", "午后三点", 208, 30),
    Track(11, "慢速下坠", "Gravity", "Free Fall", 334, 250),
    Track(12, "光年之外的晚安", "Lunara", "深空电台", 241, 276),
    Track(13, "无声的潮", "沐眠", "月光白", 297, 190),
    Track(14, "夜航西飞", "夜航员", "Orbit", 225, 205),
    Track(15, "把月亮折起来", "折光", "Polaris", 236, 300),
    Track(16, "极夜微光", "Aurora", "Polar", 312, 172),
    Track(17, "雾气里的信号", "林间有风", "Ambient No.4", 279, 262),
    Track(18, "第二次日出", "Lunara", "深空电台", 258, 286),
]

PLAYLISTS: list[Playlist] = [
    Playlist(101, "每日月相 · 今晚是上弦月", "Lunara 编辑部", 2_840_000, 258, "每日推荐"),
    Playlist(102, "私人漫游 · 只属于你的星轨", "私人漫游", 1_260_000, 268, "私人漫游"),
    Playlist(103, "深夜电台：给失眠的人", "夜航员", 8_420_000, 244, "助眠"),
    Playlist(104, "星尘收集计划 Vol.7", "折光", 942_000, 292, "电子"),
    Playlist(105, "月光下的钢琴独白", "沐眠", 12_600_000, 196, "轻音乐"),
    Playlist(106, "潮汐白噪音 · 47 分钟", "潮汐研究所", 3_150_000, 190, "白噪音"),
    Playlist(107, "银河尽头的后摇", "Silent Crater", 5_780_000, 214, "后摇"),
    Playlist(108, "凌晨四点，城市在呼吸", "林间有风", 1_890_000, 280, "氛围"),
    Playlist(109, "月海拾音 · 本周新声", "Lunara 编辑部", 620_000, 322, "新歌"),
    Playlist(110, "把星星装进口袋", "小满", 4_030_000, 250, "民谣"),
]

BANNERS = [
    {"title": "每日月相", "subtitle": "今晚是上弦月 · 为你挑选 30 首静谧之作",
     "tag": "DAILY", "hue": 258, "seed": 9001},
    {"title": "私人漫游", "subtitle": "沿着你的星轨，一直播放下去", "tag": "ROAM",
     "hue": 214, "seed": 9002},
    {"title": "潮汐视频", "subtitle": "月海实录 · 4K 沉浸影像", "tag": "VIDEO",
     "hue": 190, "seed": 9003},
]

# 演示歌词（(毫秒, 文本)）
LYRICS: list[tuple[int, str]] = [
    (0, "月海拾音 · Lunara"),
    (6000, "把窗推开 让夜进来"),
    (11000, "星尘落在 我的窗台"),
    (16000, "你说月亮 也曾离开"),
    (21500, "只是潮汐 记得回来"),
    (27000, "我沿着 星轨慢慢走"),
    (32500, "走过环形山 与深秋"),
    (38000, "所有沉默 都有回声"),
    (43500, "在银河尽头 等你转身"),
    (49000, "月光白 月光白"),
    (54500, "照见我心里 那片海"),
    (60000, "若你听见 我在唱"),
    (65500, "请把今夜 轻轻收藏"),
    (71000, "星轨在转 时间很慢"),
    (76500, "我们不说话 也很好看"),
    (82000, "等一场 迟到的日出"),
    (87500, "把整个宇宙 都照亮"),
    (93000, "月光白 月光白"),
    (98500, "照见我心里 那片海"),
    (104000, "若你听见 我在唱"),
    (109500, "请把今夜 轻轻收藏"),
    (115000, "—— 完 ——"),
]

# 演示用：给每个歌单循环分配曲目
for _i, _pl in enumerate(PLAYLISTS):
    _start = (_i * 3) % len(TRACKS)
    _pl.tracks = (TRACKS[_start:] + TRACKS[:_start])[: 8 + (_i % 5)]

# 演示用：下载任务列表
DOWNLOADS: list[DownloadTask] = []
for _idx, _t in enumerate(TRACKS[:9]):
    _task = DownloadTask(track=_t, size_mb=round(_t.duration * 0.042, 1))
    if _idx < 3:
        _task.progress = (0.18, 0.46, 0.72)[_idx]
        _task.speed = (2.4, 1.8, 3.1)[_idx]
    elif _idx == 3:
        _task.progress, _task.state = 0.55, "paused"
    elif _idx == 8:
        _task.progress, _task.state = 0.30, "failed"
        _task.error = "网络中断，已自动重试 3 次"
    else:
        _task.progress, _task.state = 1.0, "done"
    DOWNLOADS.append(_task)
