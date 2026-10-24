"""喜欢接口：参数拼装、写操作不走缓存。"""
from __future__ import annotations

from typing import Any

import pytest

from lunara.api.modules.song import like_song


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def call(self, endpoint: Any, params: Any = None, **kwargs: Any) -> Any:
        self.calls.append({"path": endpoint.path, "params": params, "kwargs": kwargs})

        class _Result:
            playlist_id = 9687758128

        return _Result()


async def test_like_sends_expected_params() -> None:
    client = RecordingClient()

    playlist_id = await like_song(client, 287398, True)  # type: ignore[arg-type]

    call = client.calls[0]
    assert call["path"] == "/api/song/like"
    assert call["params"] == {"trackId": 287398, "like": "true", "time": 0}
    assert call["kwargs"]["cache"] == "none"
    assert playlist_id == 9687758128


async def test_unlike_sends_false() -> None:
    client = RecordingClient()

    await like_song(client, 287398, False)  # type: ignore[arg-type]

    assert client.calls[0]["params"]["like"] == "false"


async def test_like_rejects_bad_id() -> None:
    client = RecordingClient()

    with pytest.raises(ValueError):
        await like_song(client, 0, True)  # type: ignore[arg-type]
