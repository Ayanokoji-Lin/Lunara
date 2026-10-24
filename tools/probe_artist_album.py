"""探针：歌手页 / 专辑页要用到的接口，逐条试路径并打印真实结构。

    .venv/Scripts/python.exe tools/probe_artist_album.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel, ConfigDict  # noqa: E402

from lunara.api import ApiClient  # noqa: E402
from lunara.api.core.logging import configure  # noqa: E402
from lunara.api.endpoints import Endpoint  # noqa: E402
from lunara.api.errors import ApiError  # noqa: E402

ARTIST_ID = 6452          # 周杰伦
ALBUM_ID = 32311          # 一张周杰伦专辑（jay）

CANDIDATES: list[tuple[str, str, dict]] = [
    ("artist v1", "/api/v1/artist/{id}", {}),
    ("artist detail", "/api/artist/detail", {"id": ARTIST_ID}),
    ("artist detail v1", "/api/v1/artist/detail/{id}", {}),
    ("artist top song", "/api/artist/top/song", {"id": ARTIST_ID}),
    ("artist songs", "/api/v1/artist/songs", {"id": ARTIST_ID, "limit": 20, "offset": 0}),
    ("album v1", "/api/v1/album/{id}", {}),
    ("album detail", "/api/v1/album/detail/{id}", {}),
]

IDS = {"{id}": None}     # 占位，实际按候选替换


class Raw(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


async def try_one(client: ApiClient, name: str, path: str, params: dict, ident: int) -> None:
    real_path = path.replace("{id}", str(ident))
    endpoint = Endpoint(real_path, True, "探针")
    try:
        result = await client.call(endpoint, params, model=Raw, unwrap="none", cache="none")
        data = result.model_dump()
        code = data.get("code")
        keys = [k for k in data if k not in ("code",)]
        print(f"\n[{name}] {real_path} → code={code} keys={keys[:8]}")
        _preview(data)
    except ApiError as exc:
        print(f"\n[{name}] {real_path} → {exc.code.value}")


def _preview(data: dict) -> None:
    for key in ("artist", "songs", "album", "hotSongs", "song"):
        value = data.get(key)
        if isinstance(value, dict):
            print(f"  {key}: dict keys={list(value)[:12]}")
            print(f"    name={value.get('name')!r} picUrl={str(value.get('picUrl'))[:60]!r}")
        elif isinstance(value, list) and value:
            print(f"  {key}: list[{len(value)}] first keys={list(value[0])[:12]}")
            first = value[0]
            print(f"    name={first.get('name')!r} al={bool(first.get('al'))} ar={bool(first.get('ar'))}")


async def main() -> int:
    configure()
    async with ApiClient() as client:
        for name, path, params in CANDIDATES:
            ident = ALBUM_ID if "album" in name else ARTIST_ID
            await try_one(client, name, path, params, ident)

    # 存一份成功样本，后面写模型时对照
    fixtures = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
    async with ApiClient() as client:
        for name, path, ident, target in (
            ("artist_v1", "/api/v1/artist/{id}", ARTIST_ID, "artist_detail"),
            ("album_v1", "/api/v1/album/{id}", ALBUM_ID, "album_detail"),
        ):
            endpoint = Endpoint(path, True, "探针")
            try:
                result = await client.call(endpoint, {}, model=Raw, unwrap="none", cache="none")
            except ApiError:
                continue
            data = result.model_dump()
            _trim(data)
            (fixtures / f"{target}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\n已保存 {target}.json（{len(json.dumps(data)) // 1024} KB）")
    return 0


def _trim(data: dict) -> None:
    """裁掉体积大又没用的字段，夹具别太胖。"""
    songs = data.get("hotSongs") or data.get("songs")
    if isinstance(songs, list):
        keep = songs[:5]
        for song in keep:
            for junk in ("rtUrls", "songFeature", "tagPicList", "privilege", "alg"):
                song.pop(junk, None)
        if "hotSongs" in data:
            data["hotSongs"] = keep
        else:
            data["songs"] = keep
    album = data.get("album")
    if isinstance(album, dict):
        album["songs"] = (album.get("songs") or [])[:5]
        album.pop("description", None)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
