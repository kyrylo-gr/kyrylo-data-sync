import asyncio
import importlib
import json
import os
import stat
import sys
import warnings
from types import SimpleNamespace

import pytest
import requests
import responses

from kdata import (
    KeyringUnavailableError,
    TokenNotFoundError,
    config,
    delete_token,
    get,
    get_saved_tokens,
    get_suppress_errors,
    get_token_storage,
    get_value,
    key_data,
    push,
    save_token,
    set_suppress_errors,
    token_settings_path,
)

TOKEN = "test-token"
BASE_URL = "https://mock.test"


@pytest.fixture(autouse=True)
def reset_suppress_errors():
    set_suppress_errors(False)
    yield
    set_suppress_errors(False)


@responses.activate
def test_get_sends_expected_request_and_returns_json():
    responses.add(
        responses.GET,
        f"{BASE_URL}/memo/example",
        json={"value": {"hello": "world"}},
        status=200,
    )

    result = get("example", TOKEN, url=BASE_URL)

    assert result == {"value": {"hello": "world"}}
    request = responses.calls[0].request
    assert request.method == "GET"
    assert request.url == f"{BASE_URL}/memo/example"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert "test-token" not in request.url
    assert request.body is None


@responses.activate
def test_push_sends_expected_request_and_returns_json():
    responses.add(
        responses.POST,
        f"{BASE_URL}/memo/example",
        json={"ok": True},
        status=200,
    )

    result = push("example", {"hello": "world"}, TOKEN, url=BASE_URL)

    assert result == {"ok": True}
    request = responses.calls[0].request
    assert request.method == "POST"
    assert request.url == f"{BASE_URL}/memo/example"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    payload = json.loads(request.body)
    assert payload == {"value": {"hello": "world"}}
    assert "token" not in payload
    assert TOKEN not in request.url


@pytest.mark.parametrize(
    "value",
    [
        "json string",
        ["list"],
        ("tuple",),
        b"bytes",
    ],
)
def test_push_rejects_non_dictionary_values(value):
    with pytest.raises(TypeError):
        push("example", value, TOKEN, url=BASE_URL)


def test_push_accepts_value_at_1024_byte_limit():
    value = {"data": "x" * 1013}

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"{BASE_URL}/memo/example",
            json={"ok": True},
            status=200,
        )

        assert push("example", value, TOKEN, url=BASE_URL) == {"ok": True}


def test_push_rejects_value_greater_than_1024_bytes():
    value = {"data": "x" * 1014}

    with pytest.raises(ValueError, match="at most 1024 bytes"):
        push("example", value, TOKEN, url=BASE_URL)


def test_push_rejects_non_json_serializable_dictionary():
    with pytest.raises(ValueError, match="JSON serializable"):
        push("example", {"bad": object()}, TOKEN, url=BASE_URL)


def test_suppress_errors_converts_validation_errors_to_warnings():
    set_suppress_errors(True)

    with pytest.warns(RuntimeWarning, match="kdata ignored an error in push"):
        assert push("example", "json string", TOKEN, url=BASE_URL) is None


def test_suppress_errors_converts_missing_token_errors_to_warnings(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(key_data, "import_module", _raise_import_error)
    set_suppress_errors(True)

    with pytest.warns(RuntimeWarning, match="KDATA_TOKEN_EXAMPLE"):
        assert get("example", url=BASE_URL) is None


def test_suppress_errors_can_be_disabled():
    set_suppress_errors(True)
    assert get_suppress_errors() is True
    set_suppress_errors(False)

    with pytest.raises(TypeError):
        push("example", "json string", TOKEN, url=BASE_URL)


def test_suppress_errors_does_not_raise_when_warnings_are_errors():
    set_suppress_errors(True)

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        assert push("example", "json string", TOKEN, url=BASE_URL) is None


@pytest.mark.parametrize("func,args", [(get, ("", TOKEN)), (push, ("", {}, TOKEN))])
def test_functions_validate_empty_key(func, args):
    with pytest.raises(ValueError, match="key"):
        func(*args, url=BASE_URL)


@pytest.mark.parametrize(
    "func,args",
    [(get, ("example", "")), (push, ("example", {}, ""))],
)
def test_functions_validate_empty_token(func, args):
    with pytest.raises(ValueError, match="token"):
        func(*args, url=BASE_URL)


@pytest.mark.parametrize(
    "func,args",
    [(get, ("example", TOKEN)), (push, ("example", {}, TOKEN))],
)
def test_functions_validate_empty_url(func, args):
    with pytest.raises(ValueError, match="url"):
        func(*args, url="")


@pytest.mark.parametrize("method,func,args", [
    (responses.GET, get, ("example", TOKEN)),
    (responses.POST, push, ("example", {}, TOKEN)),
])
def test_functions_warn_for_http_error_responses(method, func, args):
    with responses.RequestsMock() as rsps:
        rsps.add(method, f"{BASE_URL}/memo/example", json={"error": "no"}, status=500)

        with pytest.warns(RuntimeWarning, match="HTTP 500"):
            assert func(*args, url=BASE_URL) is None


@pytest.mark.parametrize("request_name,func,args", [
    ("get", get, ("example", TOKEN)),
    ("post", push, ("example", {}, TOKEN)),
])
def test_functions_warn_for_connection_failures(monkeypatch, request_name, func, args):
    def fail_request(*_args, **_kwargs):
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(key_data.requests, request_name, fail_request)

    with pytest.warns(RuntimeWarning, match="network down"):
        assert func(*args, url=BASE_URL) is None


@pytest.mark.parametrize("method,func,args", [
    (responses.GET, get, ("example", TOKEN)),
    (responses.POST, push, ("example", {}, TOKEN)),
])
def test_functions_use_configured_base_url(monkeypatch, method, func, args):
    monkeypatch.setattr(config, "BASE_URL", BASE_URL)

    with responses.RequestsMock() as rsps:
        rsps.add(method, f"{BASE_URL}/memo/example", json={"ok": True}, status=200)

        assert func(*args) == {"ok": True}


@pytest.mark.parametrize("method,func,args", [
    (responses.GET, get, ("example", TOKEN)),
    (responses.POST, push, ("example", {}, TOKEN)),
])
def test_functions_use_override_url_with_trailing_slash(method, func, args):
    with responses.RequestsMock() as rsps:
        rsps.add(method, f"{BASE_URL}/memo/example", json={"ok": True}, status=200)

        assert func(*args, url=f"{BASE_URL}/") == {"ok": True}


@responses.activate
def test_get_uses_keyed_environment_token(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KDATA_TOKEN_EXAMPLE_KEY", "env-token")
    monkeypatch.setenv("KDATA_TOKEN", "global-token")
    responses.add(
        responses.GET,
        f"{BASE_URL}/memo/example-key",
        json={"ok": True},
        status=200,
    )

    assert get("example-key", url=BASE_URL) == {"ok": True}

    request = responses.calls[0].request
    assert request.headers["Authorization"] == "Bearer env-token"


@responses.activate
def test_get_does_not_use_global_environment_token(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KDATA_TOKEN", "global-token")
    monkeypatch.setattr(key_data, "import_module", _raise_import_error)
    responses.add(
        responses.GET,
        f"{BASE_URL}/memo/example",
        json={"ok": True},
        status=200,
    )

    with pytest.raises(TokenNotFoundError, match="KDATA_TOKEN_EXAMPLE"):
        get("example", url=BASE_URL)

    assert len(responses.calls) == 0


@responses.activate
def test_get_uses_project_settings_file_token(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    save_token("example", "file-token")
    responses.add(
        responses.GET,
        f"{BASE_URL}/memo/example",
        json={"ok": True},
        status=200,
    )

    assert get("example", url=BASE_URL) == {"ok": True}

    request = responses.calls[0].request
    assert request.headers["Authorization"] == "Bearer file-token"


@responses.activate
def test_get_uses_keyring_token_after_file_miss(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    fake_keyring = _fake_keyring({("kdata", "example"): "keyring-token"})
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    responses.add(
        responses.GET,
        f"{BASE_URL}/memo/example",
        json={"ok": True},
        status=200,
    )

    assert get("example", url=BASE_URL) == {"ok": True}

    request = responses.calls[0].request
    assert request.headers["Authorization"] == "Bearer keyring-token"


@responses.activate
def test_explicit_token_takes_precedence(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KDATA_TOKEN_EXAMPLE", "env-token")
    save_token("example", "file-token")
    responses.add(
        responses.GET,
        f"{BASE_URL}/memo/example",
        json={"ok": True},
        status=200,
    )

    assert get("example", "explicit-token", url=BASE_URL) == {"ok": True}

    request = responses.calls[0].request
    assert request.headers["Authorization"] == "Bearer explicit-token"


def test_save_token_writes_project_settings_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    save_token("memo-key", "file-token")

    assert token_settings_path() == tmp_path / ".kdata.json"
    settings = json.loads(token_settings_path().read_text(encoding="utf-8"))
    assert settings == {
        "version": 1,
        "keyring_tokens": [],
        "tokens": {"memo-key": "file-token"},
    }
    if os.name != "nt":
        assert stat.S_IMODE(token_settings_path().stat().st_mode) == 0o600


def test_delete_token_removes_project_settings_file_entry(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    save_token("memo-key", "file-token")
    save_token("other-key", "other-token")

    delete_token("memo-key")

    settings = json.loads(token_settings_path().read_text(encoding="utf-8"))
    assert settings == {
        "version": 1,
        "keyring_tokens": [],
        "tokens": {"other-key": "other-token"},
    }


def test_delete_token_does_not_create_missing_settings_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    delete_token("memo-key")

    assert not token_settings_path().exists()


def test_malformed_project_settings_file_raises_clear_error(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    token_settings_path().write_text("{nope", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed JSON"):
        get("example", url=BASE_URL)


def test_missing_token_raises_specific_error(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    save_token("other-key", "file-token")
    monkeypatch.setattr(key_data, "import_module", _raise_import_error)

    with pytest.raises(TokenNotFoundError, match=r"KDATA_TOKEN_EXAMPLE.*\.kdata\.json"):
        get("example", url=BASE_URL)


def test_save_token_can_store_in_keyring(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    fake_keyring = _fake_keyring()
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

    save_token("memo-key", "keyring-token", storage="keyring")

    assert fake_keyring.passwords == {("kdata", "memo-key"): "keyring-token"}
    settings = json.loads(token_settings_path().read_text(encoding="utf-8"))
    assert settings == {"version": 1, "keyring_tokens": ["memo-key"], "tokens": {}}


def test_save_token_can_store_in_both_locations(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    fake_keyring = _fake_keyring()
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

    save_token("memo-key", "token", storage="both")

    settings = json.loads(token_settings_path().read_text(encoding="utf-8"))
    assert settings["tokens"] == {"memo-key": "token"}
    assert settings["keyring_tokens"] == ["memo-key"]
    assert fake_keyring.passwords == {("kdata", "memo-key"): "token"}


def test_delete_token_can_remove_from_keyring(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    fake_keyring = _fake_keyring()
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    save_token("memo-key", "token", storage="keyring")

    delete_token("memo-key", storage="keyring")

    assert fake_keyring.passwords == {}
    assert json.loads(token_settings_path().read_text(encoding="utf-8")) == {
        "version": 1,
        "keyring_tokens": [],
        "tokens": {},
    }


def test_keyring_storage_requires_optional_dependency(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(key_data, "import_module", _raise_import_error)

    with pytest.raises(KeyringUnavailableError, match=r"kdata\[keyring\]"):
        save_token("memo-key", "token", storage="keyring")


def test_both_storage_requires_keyring_before_writing_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(key_data, "import_module", _raise_import_error)

    with pytest.raises(KeyringUnavailableError):
        save_token("memo-key", "token", storage="both")

    assert not token_settings_path().exists()


def test_rejects_unknown_storage():
    with pytest.raises(ValueError, match="storage"):
        save_token("memo-key", "token", storage="database")


def test_get_saved_tokens_reports_file_keyring_and_both(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    fake_keyring = _fake_keyring()
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    save_token("file-key", "file-token")
    save_token("keyring-key", "keyring-token", storage="keyring")
    save_token("both-key", "both-token", storage="both")

    assert get_saved_tokens() == {
        "both-key": "both",
        "file-key": "file",
        "keyring-key": "keyring",
    }


def test_get_token_storage_reports_saved_storage(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    fake_keyring = _fake_keyring({("kdata", "external-key"): "external-token"})
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    save_token("file-key", "file-token")
    save_token("keyring-key", "keyring-token", storage="keyring")
    save_token("both-key", "both-token", storage="both")

    assert get_token_storage("file-key") == "file"
    assert get_token_storage("keyring-key") == "keyring"
    assert get_token_storage("both-key") == "both"
    assert get_token_storage("external-key") == "keyring"
    assert get_token_storage("missing-key") is None


@responses.activate
def test_get_value_returns_response_value(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    responses.add(
        responses.GET,
        f"{BASE_URL}/memo/example",
        json={"value": {"hello": "world"}},
        status=200,
    )

    assert get_value("example", TOKEN, url=BASE_URL) == {"hello": "world"}


@responses.activate
def test_get_value_returns_none_when_get_is_ignored():
    responses.add(
        responses.GET,
        f"{BASE_URL}/memo/example",
        json={"error": "no"},
        status=503,
    )

    with pytest.warns(RuntimeWarning, match="HTTP 503"):
        assert get_value("example", TOKEN, url=BASE_URL) is None


def test_async_module_exposes_front_functions(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    async_kdata = importlib.import_module("kdata.aio")

    async def run():
        await async_kdata.save_token("example", TOKEN)
        assert await async_kdata.get_saved_tokens() == {"example": "file"}
        assert await async_kdata.get_token_storage("example") == "file"
        assert await async_kdata.token_settings_path() == token_settings_path()
        await async_kdata.delete_token("example")
        assert await async_kdata.get_saved_tokens() == {}

    asyncio.run(run())


@responses.activate
def test_async_get_and_push_are_awaitable():
    async_kdata = importlib.import_module("kdata.aio")
    responses.add(
        responses.GET,
        f"{BASE_URL}/memo/example",
        json={"value": {"hello": "world"}},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/memo/example",
        json={"value": {"hello": "world"}},
        status=200,
    )
    responses.add(
        responses.POST,
        f"{BASE_URL}/memo/example",
        json={"ok": True},
        status=200,
    )

    async def run():
        assert await async_kdata.get("example", TOKEN, url=BASE_URL) == {
            "value": {"hello": "world"}
        }
        assert await async_kdata.get_value("example", TOKEN, url=BASE_URL) == {
            "hello": "world"
        }
        assert await async_kdata.push("example", {}, TOKEN, url=BASE_URL) == {
            "ok": True
        }

    asyncio.run(run())


def test_async_suppress_errors_converts_errors_to_warnings():
    async_kdata = importlib.import_module("kdata.aio")

    async def run():
        async_kdata.set_suppress_errors(True)
        assert async_kdata.get_suppress_errors() is True
        with pytest.warns(RuntimeWarning, match="kdata ignored an error in push"):
            assert await async_kdata.push(
                "example", "json string", TOKEN, url=BASE_URL
            ) is None

    asyncio.run(run())


def _raise_import_error(name):
    raise ImportError(name)


def _fake_keyring(initial_passwords=None):
    class KeyringError(Exception):
        pass

    passwords = dict(initial_passwords or {})

    def get_password(service, username):
        return passwords.get((service, username))

    def set_password(service, username, password):
        passwords[(service, username)] = password

    def delete_password(service, username):
        passwords.pop((service, username), None)

    return SimpleNamespace(
        passwords=passwords,
        errors=SimpleNamespace(
            KeyringError=KeyringError,
            NoKeyringError=KeyringError,
            PasswordSetError=KeyringError,
            PasswordDeleteError=KeyringError,
        ),
        get_password=get_password,
        set_password=set_password,
        delete_password=delete_password,
    )
