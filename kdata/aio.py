import asyncio
from functools import wraps
from pathlib import Path
from typing import Optional

from . import key_data as _sync

KeyringUnavailableError = _sync.KeyringUnavailableError
TokenNotFoundError = _sync.TokenNotFoundError


def _warn_on_error(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            if not _sync.get_suppress_errors():
                raise
            _sync._warn_ignored(f"kdata ignored an error in {func.__name__}: {exc}")
            return None

    return wrapper


def set_suppress_errors(enabled: bool = True) -> None:
    _sync.set_suppress_errors(enabled)


def get_suppress_errors() -> bool:
    return _sync.get_suppress_errors()


@_warn_on_error
async def save_token(key: str, token: str, *, storage: str = "file") -> None:
    await asyncio.to_thread(_sync.save_token, key, token, storage=storage)


@_warn_on_error
async def delete_token(key: str, *, storage: str = "file") -> None:
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
    timeout: Optional[float] = _sync.REQUEST_TIMEOUT_SECONDS,
) -> Optional[object]:
    return await asyncio.to_thread(_sync.push, key, value, token, url, timeout=timeout)


__all__ = [
    "KeyringUnavailableError",
    "TokenNotFoundError",
    "delete_token",
    "get",
    "get_saved_tokens",
    "get_suppress_errors",
    "get_token_storage",
    "get_value",
    "push",
    "save_token",
    "set_suppress_errors",
    "token_settings_path",
]
