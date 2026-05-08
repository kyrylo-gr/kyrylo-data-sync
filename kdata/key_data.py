import json
from typing import Optional

import requests

from . import config

MAX_VALUE_BYTES = 1024


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


def _parse_response(response: requests.Response) -> object:
    response.raise_for_status()
    return response.json()


def _base_url(url: Optional[str]) -> str:
    return _validate_base_url(config.BASE_URL if url is None else url)


def get(key: str, token: str, url: Optional[str] = None) -> object:
    _validate_key(key)
    _validate_token(token)

    response = requests.get(
        _build_url(_base_url(url), key),
        headers=_build_auth_headers(token),
    )
    return _parse_response(response)


def push(key: str, value: dict, token: str, url: Optional[str] = None) -> object:
    _validate_key(key)
    _validate_token(token)
    _validate_value(value)

    response = requests.post(
        _build_url(_base_url(url), key),
        headers=_build_auth_headers(token),
        json={"value": value},
    )
    return _parse_response(response)
