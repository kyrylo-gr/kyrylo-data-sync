import json

import pytest
import requests
import responses

from kdata import config, get, push

TOKEN = "test-token"
BASE_URL = "https://mock.test"


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
def test_functions_raise_for_http_error_responses(method, func, args):
    with responses.RequestsMock() as rsps:
        rsps.add(method, f"{BASE_URL}/memo/example", json={"error": "no"}, status=500)

        with pytest.raises(requests.HTTPError):
            func(*args, url=BASE_URL)


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
