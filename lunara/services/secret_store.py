"""登录态的本地加密存储。

设计取舍：
- Windows 上优先用 **DPAPI**（`CryptProtectData`）——密钥由系统按当前用户托管，
  应用自己不持有任何密钥，拷走文件到别的账户也解不开。
- DPAPI 不可用（非 Windows、或被安全软件拦）时退回 **AES-256-GCM**，
  密钥取 ``LUNARA_SECRET_KEY`` 环境变量，没有就生成 ``key.bin`` 放在同一目录。
- 文件格式：``b"LNR1"`` + 1 字节模式（``D``=DPAPI / ``A``=AES-GCM）+ 载荷。
  AES 载荷 = 12 字节 nonce + 密文（含 tag）。

失败一律返回 ``None``，绝不抛给调用方——登录态读不出来最多是「回到未登录」，
不该让应用起不来。
"""
from __future__ import annotations

import base64
import ctypes
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

APP_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "Lunara"
SESSION_FILE = APP_DIR / "session.enc"
KEY_FILE = APP_DIR / "key.bin"

MAGIC = b"LNR1"
MODE_DPAPI = b"D"
MODE_AES = b"A"

#: CryptProtectData 的 flag：不弹 UI（后台调用必须加）
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _to_blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:  # type: ignore[type-arg]
    buffer = ctypes.create_string_buffer(data, len(data))
    blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    return blob, buffer  # 必须把 buffer 一起返回，否则会被 GC 掉


def _dpapi_protect(data: bytes) -> bytes | None:
    if os.name != "nt":
        return None
    try:
        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        blob_in, _keep = _to_blob(data)
        blob_out = _DataBlob()
        ok = crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None,
            _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out),
        )
        if not ok:
            return None
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))
    except Exception:  # noqa: BLE001 - 任何异常都视为「DPAPI 不可用」
        return None


def _dpapi_unprotect(data: bytes) -> bytes | None:
    if os.name != "nt":
        return None
    try:
        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        blob_in, _keep = _to_blob(data)
        blob_out = _DataBlob()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None,
            _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out),
        )
        if not ok:
            return None
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))
    except Exception:  # noqa: BLE001
        return None


def _load_key() -> bytes:
    """AES 回退路径的主密钥：环境变量 > 本地 key.bin > 新生成。"""
    env = os.environ.get("LUNARA_SECRET_KEY")
    if env:
        raw = bytes.fromhex(env) if len(env) == 64 else base64.b64decode(env)
        if len(raw) == 32:
            return raw
    if KEY_FILE.exists():
        key = KEY_FILE.read_bytes()
        if len(key) == 32:
            return key
    key = AESGCM.generate_key(bit_length=256)
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_bytes(key)
    return key


@dataclass
class SecretStore:
    """一个 JSON 载荷的加密读写。"""

    path: Path = SESSION_FILE
    force_aes: bool = False

    # ------------------------------------------------------------------ #
    @property
    def exists(self) -> bool:
        return self.path.exists()

    def save(self, payload: Mapping[str, Any]) -> bool:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        sealed = None if self.force_aes else _dpapi_protect(data)
        if sealed is not None:
            blob = MAGIC + MODE_DPAPI + sealed
        else:
            key = _load_key()
            nonce = os.urandom(12)
            blob = MAGIC + MODE_AES + nonce + AESGCM(key).encrypt(nonce, data, None)

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(blob)
            return True
        except OSError:
            return False

    def load(self) -> dict[str, Any] | None:
        try:
            blob = self.path.read_bytes()
        except OSError:
            return None
        if len(blob) < len(MAGIC) + 1 or not blob.startswith(MAGIC):
            return None

        mode = blob[len(MAGIC):len(MAGIC) + 1]
        payload = blob[len(MAGIC) + 1:]
        if mode == MODE_DPAPI:
            plain = _dpapi_unprotect(payload)
        elif mode == MODE_AES:
            if len(payload) <= 12:
                return None
            try:
                plain = AESGCM(_load_key()).decrypt(payload[:12], payload[12:], None)
            except Exception:  # noqa: BLE001 - 密钥不匹配或文件损坏
                return None
        else:
            return None

        if plain is None:
            return None
        try:
            data = json.loads(plain.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    @property
    def backend(self) -> str:
        """当前会用的加密方式，仅用于日志/诊断。"""
        if self.force_aes or os.name != "nt":
            return "aes-gcm"
        return "dpapi"
