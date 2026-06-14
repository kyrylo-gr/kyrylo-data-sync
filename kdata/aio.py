import asyncio
from functools import wraps
from pathlib import Path
from typing import Literal, Optional

from . import config
from . import key_data as _sync

KeyringUnavailableError = _sync.KeyringUnavailableError
TokenNotFoundError = _sync.TokenNotFoundError


def _warn_on_error(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            if not config.SUPPRESS_ERRORS:
                raise
            _sync._warn_ignored(f"kdata ignored an error in {func.__name__}: {exc}")
            return None

    return wrapper


@_warn_on_error
async def copy_token(
    src_key: str,
    dst_key: str,
    *,
    src_storage: Optional[Literal["file", "keyring", "both"]] = None,
    dst_storage: Optional[Literal["file", "keyring", "both"]] = None,
) -> None:
    await asyncio.to_thread(
        _sync.copy_token,
        src_key,
        dst_key,
        src_storage=src_storage,
        dst_storage=dst_storage,
    )


@_warn_on_error
async def save_token(
    key: str, token: str, *, storage: Literal["file", "keyring", "both"] = "file"
) -> None:
    await asyncio.to_thread(_sync.save_token, key, token, storage=storage)


@_warn_on_error
async def delete_token(
    key: str, *, storage: Literal["file", "keyring", "both"] = "file"
) -> None:
    await asyncio.to_thread(_sync.delete_token, key, storage=storage)


@_warn_on_error
async def get_saved_tokens() -> dict:
    return await asyncio.to_thread(_sync.get_saved_tokens)


@_warn_on_error
async def get_token_storage(key: str) -> Optional[str]:
    return await asyncio.to_thread(_sync.get_token_storage, key)


@_warn_on_error
async def token_settings_path() -> Path:
    return await asyncio.to_thread(_sync.token_settings_path)


@_warn_on_error
async def get(
    key: str,
    token: Optional[str] = None,
    url: Optional[str] = None,
    *,
    timeout: Optional[float] = _sync.REQUEST_TIMEOUT_SECONDS,
) -> Optional[object]:
    return await asyncio.to_thread(_sync.get, key, token, url, timeout=timeout)


@_warn_on_error
async def get_value(
    key: str,
    token: Optional[str] = None,
    url: Optional[str] = None,
    *,
    timeout: Optional[float] = _sync.REQUEST_TIMEOUT_SECONDS,
) -> Optional[object]:
    return await asyncio.to_thread(_sync.get_value, key, token, url, timeout=timeout)


@_warn_on_error
async def push(
    key: str,
    value: dict,
    token: Optional[str] = None,
    url: Optional[str] = None,
    *,
    notify: bool = False,
    timeout: Optional[float] = _sync.REQUEST_TIMEOUT_SECONDS,
) -> Optional[object]:
    return await asyncio.to_thread(
        _sync.push, key, value, token, url, notify=notify, timeout=timeout
    )


__all__ = [
    "KeyringUnavailableError",
    "TokenNotFoundError",
    "copy_token",
    "delete_token",
    "get",
    "get_saved_tokens",
    "get_token_storage",
    "get_value",
    "push",
    "save_token",
    "token_settings_path",
]
