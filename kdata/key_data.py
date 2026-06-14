import json
import os
import re
import tempfile
import warnings
from contextlib import suppress
from functools import wraps
from importlib import import_module
from pathlib import Path
from typing import Optional

import requests

from . import config

MAX_VALUE_BYTES = 1024
REQUEST_TIMEOUT_SECONDS = 5
SETTINGS_FILENAME = ".kdata.json"
SETTINGS_VERSION = 1
KEYRING_SERVICE = "kdata"
VALID_STORAGE = {"file", "keyring", "both"}
SUPPRESS_ERRORS = True


class TokenNotFoundError(ValueError):
    """Raised when no token can be resolved for a memo key."""


class KeyringUnavailableError(RuntimeError):
    """Raised when keyring storage is requested but unavailable."""


def _warn_ignored(message: str) -> None:
    with suppress(Warning):
        warnings.warn(message, RuntimeWarning, stacklevel=3)


def _warn_on_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if not SUPPRESS_ERRORS:
                raise
            _warn_ignored(f"kdata ignored an error in {func.__name__}: {exc}")
            return None

    return wrapper


def _validate_key(key: str) -> None:
    if not isinstance(key, str) or not key:
        raise ValueError("key must be a non-empty string")


def _validate_token(token: str) -> None:
    if not isinstance(token, str) or not token:
        raise ValueError("token must be a non-empty string")


def _validate_base_url(url: str) -> str:
    if not isinstance(url, str) or not url:
        raise ValueError("url must be a non-empty string")
    return url.rstrip("/")


def _build_url(base_url: str, key: str) -> str:
    return f"{base_url}/memo/{key}"


def _build_auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _validate_storage(storage: str) -> None:
    if storage not in VALID_STORAGE:
        raise ValueError("storage must be one of: file, keyring, both")


def _token_env_var(key: str) -> str:
    normalized_key = re.sub(r"[^A-Z0-9]", "_", key.upper())
    return f"KDATA_TOKEN_{normalized_key}"


def _token_settings_path() -> Path:
    return Path.cwd() / SETTINGS_FILENAME


@_warn_on_error
def token_settings_path() -> Path:
    return _token_settings_path()


def _empty_settings() -> dict:
    return {"version": SETTINGS_VERSION, "tokens": {}, "keyring_tokens": []}


def _read_settings(path: Optional[Path] = None) -> dict:
    settings_path = _token_settings_path() if path is None else path
    if not settings_path.exists():
        return _empty_settings()

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{settings_path} contains malformed JSON") from exc

    if (
        not isinstance(settings, dict)
        or settings.get("version") != SETTINGS_VERSION
        or not isinstance(settings.get("tokens"), dict)
    ):
        raise ValueError(
            f"{settings_path} must contain version {SETTINGS_VERSION} "
            "and a tokens object"
        )

    for memo_key, token in settings["tokens"].items():
        if not isinstance(memo_key, str) or not isinstance(token, str):
            raise ValueError(f"{settings_path} tokens must map strings to strings")

    if "keyring_tokens" not in settings:
        settings["keyring_tokens"] = []
    if not isinstance(settings["keyring_tokens"], list) or not all(
        isinstance(memo_key, str) for memo_key in settings["keyring_tokens"]
    ):
        raise ValueError(f"{settings_path} keyring_tokens must be a list of strings")

    return settings


def _write_settings(settings: dict, path: Optional[Path] = None) -> None:
    settings_path = _token_settings_path() if path is None else path
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(settings, indent=2, sort_keys=True) + "\n"

    fd, temp_name = tempfile.mkstemp(
        dir=settings_path.parent,
        prefix=f".{settings_path.name}.",
        text=True,
    )
    temp_path = Path(temp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            temp_file.write(encoded)
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, settings_path)
        os.chmod(settings_path, 0o600)
    except OSError:
        with suppress(OSError):
            temp_path.unlink()
        raise


def _keyring():
    try:
        return import_module("keyring")
    except ImportError as exc:
        raise KeyringUnavailableError(
            "keyring support is not installed; install kdata[keyring]"
        ) from exc


def _keyring_error_types(keyring_module: object) -> tuple:
    errors = getattr(keyring_module, "errors", None)
    names = (
        "KeyringError",
        "NoKeyringError",
        "PasswordSetError",
        "PasswordDeleteError",
    )
    return tuple(
        error_type
        for name in names
        if isinstance((error_type := getattr(errors, name, None)), type)
    )


def _get_keyring_token(key: str) -> Optional[str]:
    keyring_module = _keyring()
    try:
        return keyring_module.get_password(KEYRING_SERVICE, key)
    except _keyring_error_types(keyring_module) as exc:
        raise KeyringUnavailableError("keyring backend is unavailable") from exc


def _set_keyring_token(key: str, token: str) -> None:
    keyring_module = _keyring()
    try:
        keyring_module.set_password(KEYRING_SERVICE, key, token)
    except _keyring_error_types(keyring_module) as exc:
        raise KeyringUnavailableError("keyring backend is unavailable") from exc


def _delete_keyring_token(key: str) -> None:
    keyring_module = _keyring()
    try:
        keyring_module.delete_password(KEYRING_SERVICE, key)
    except _keyring_error_types(keyring_module) as exc:
        raise KeyringUnavailableError("keyring backend is unavailable") from exc


def _get_file_token(key: str) -> Optional[str]:
    return _read_settings()["tokens"].get(key)


def _save_file_token(key: str, token: str) -> None:
    settings = _read_settings()
    settings["tokens"][key] = token
    _write_settings(settings)


def _track_keyring_token(key: str) -> None:
    settings = _read_settings()
    keyring_tokens = set(settings["keyring_tokens"])
    keyring_tokens.add(key)
    settings["keyring_tokens"] = sorted(keyring_tokens)
    _write_settings(settings)


def _delete_file_token(key: str) -> None:
    settings_path = _token_settings_path()
    if not settings_path.exists():
        return
    settings = _read_settings(settings_path)
    settings["tokens"].pop(key, None)
    _write_settings(settings, settings_path)


def _untrack_keyring_token(key: str) -> None:
    settings_path = _token_settings_path()
    if not settings_path.exists():
        return
    settings = _read_settings(settings_path)
    settings["keyring_tokens"] = [
        memo_key for memo_key in settings["keyring_tokens"] if memo_key != key
    ]
    _write_settings(settings, settings_path)


def _storage_label(file_saved: bool, keyring_saved: bool) -> Optional[str]:
    if file_saved and keyring_saved:
        return "both"
    if file_saved:
        return "file"
    if keyring_saved:
        return "keyring"
    return None


def _has_keyring_token(key: str) -> bool:
    try:
        return bool(_get_keyring_token(key))
    except KeyringUnavailableError:
        return False


def _resolve_token(key: str, token: Optional[str]) -> str:
    if token is not None:
        _validate_token(token)
        return token

    env_var = _token_env_var(key)
    env_token = os.environ.get(env_var)
    if env_token:
        return env_token

    file_token = _get_file_token(key)
    if file_token:
        return file_token

    keyring_note = "keyring"
    try:
        keyring_token = _get_keyring_token(key)
    except KeyringUnavailableError as exc:
        keyring_note = f"keyring ({exc})"
    else:
        if keyring_token:
            return keyring_token

    raise TokenNotFoundError(
        "token was not provided and no token was found in "
        f"{env_var}, {_token_settings_path()}, or {keyring_note}"
    )


def _validate_value(value: dict) -> None:
    if not isinstance(value, dict):
        raise TypeError("value must be a dictionary")

    try:
        json_bytes = json.dumps(
            value,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("value must be JSON serializable") from exc

    if len(json_bytes) > MAX_VALUE_BYTES:
        raise ValueError("value JSON payload must be at most 1024 bytes")


def _parse_response(response: requests.Response) -> Optional[object]:
    if not response.ok:
        reason = f" {response.reason}" if response.reason else ""
        _warn_ignored(
            "kdata request was ignored because the server returned "
            f"HTTP {response.status_code}{reason}"
        )
        return None

    try:
        return response.json()
    except ValueError as exc:
        _warn_ignored(
            f"kdata request was ignored because the server returned invalid JSON: {exc}"
        )
        return None


def _request_json(method, url: str, **kwargs) -> Optional[object]:
    try:
        response = method(url, **kwargs)
    except requests.RequestException as exc:
        _warn_ignored(f"kdata request was ignored because it failed: {exc}")
        return None
    return _parse_response(response)


def _base_url(url: Optional[str]) -> str:
    return _validate_base_url(config.BASE_URL if url is None else url)


def set_suppress_errors(enabled: bool = True) -> None:
    """Control whether public kdata functions warn instead of raising errors."""
    global SUPPRESS_ERRORS
    SUPPRESS_ERRORS = bool(enabled)


def get_suppress_errors() -> bool:
    return SUPPRESS_ERRORS


@_warn_on_error
def save_token(key: str, token: str, *, storage: str = "file") -> None:
    _validate_key(key)
    _validate_token(token)
    _validate_storage(storage)

    if storage in {"keyring", "both"}:
        _set_keyring_token(key, token)
        _track_keyring_token(key)
    if storage in {"file", "both"}:
        _save_file_token(key, token)


@_warn_on_error
def delete_token(key: str, *, storage: str = "file") -> None:
    _validate_key(key)
    _validate_storage(storage)

    if storage in {"keyring", "both"}:
        _delete_keyring_token(key)
        _untrack_keyring_token(key)
    if storage in {"file", "both"}:
        _delete_file_token(key)


@_warn_on_error
def get_saved_tokens() -> dict:
    settings = _read_settings()
    saved_tokens = {
        memo_key: _storage_label(True, memo_key in settings["keyring_tokens"])
        for memo_key in settings["tokens"]
    }

    for memo_key in settings["keyring_tokens"]:
        saved_tokens.setdefault(memo_key, "keyring")

    return dict(sorted(saved_tokens.items()))


@_warn_on_error
def get_token_storage(key: str) -> Optional[str]:
    _validate_key(key)
    settings = _read_settings()
    file_saved = key in settings["tokens"]
    keyring_saved = key in settings["keyring_tokens"] or _has_keyring_token(key)
    return _storage_label(file_saved, keyring_saved)


@_warn_on_error
def get(
    key: str,
    token: Optional[str] = None,
    url: Optional[str] = None,
    *,
    timeout: Optional[float] = REQUEST_TIMEOUT_SECONDS,
) -> Optional[object]:
    _validate_key(key)
    resolved_token = _resolve_token(key, token)

    return _request_json(
        requests.get,
        _build_url(_base_url(url), key),
        headers=_build_auth_headers(resolved_token),
        timeout=timeout,
    )


@_warn_on_error
def get_value(
    key: str,
    token: Optional[str] = None,
    url: Optional[str] = None,
    *,
    timeout: Optional[float] = REQUEST_TIMEOUT_SECONDS,
) -> Optional[object]:
    response = get(key, token, url=url, timeout=timeout)
    if response is None:
        return None
    if not isinstance(response, dict) or "value" not in response:
        _warn_ignored("kdata response was ignored because it has no value field")
        return None
    return response["value"]


@_warn_on_error
def push(
    key: str,
    value: dict,
    token: Optional[str] = None,
    url: Optional[str] = None,
    *,
    notify: bool = False,
    timeout: Optional[float] = REQUEST_TIMEOUT_SECONDS,
) -> Optional[object]:
    _validate_key(key)
    resolved_token = _resolve_token(key, token)
    _validate_value(value)

    payload: dict = {"value": value}
    if notify:
        payload["notify"] = True

    return _request_json(
        requests.post,
        _build_url(_base_url(url), key),
        headers=_build_auth_headers(resolved_token),
        json=payload,
        timeout=timeout,
    )
