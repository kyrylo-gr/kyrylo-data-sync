# keyData Implementation Plan

## Project Idea

`keyData` is a very small Python library with two public functions:

- `push(key, value, token, url=None)`: send JSON-compatible dictionary data to a server with an HTTP `POST` request.
- `get(key, token, url=None)`: fetch data from the server with an HTTP `GET` request.

The server base URL should live in `src/config.py`, so callers can use the library without passing the URL every time. Tests must not call the real server. They should mock HTTP access and verify the exact request shape.

The package is intended to be installed directly from GitHub using `pip`, not published to PyPI. Local development should use a standard Python virtual environment created with `python -m venv`, not `uv`. The project therefore needs a standards-compliant `pyproject.toml`.

## Target API

The intended user-facing import should be:

```python
from keyData import push, get
```

Example usage:

```python
from keyData import push, get

token = "secret-token"

push("example-key", {"status": "ok", "count": 3}, token)
data = get("example-key", token)
```

## Directory Layout

Use the existing `src/` directory, with source files directly inside it as requested:

```text
.
├── AGENT.md
├── implementation.md
├── pyproject.toml
├── README.md
├── src
│   ├── keyData.py
│   └── config.py
└── tests
    └── test_keyData.py
```

Notes:

- Do not create `src/keyData/` or another nested package directory.
- `src/keyData.py` should expose the public `push` and `get` functions.
- `src/config.py` should contain the default base URL.
- Because this is a flat module layout, configure packaging with `setuptools` and `py-modules` in `pyproject.toml`.

## Packaging Plan

Create `pyproject.toml` using modern PEP 621 metadata.

Recommended build backend:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"
```

Recommended project metadata:

```toml
[project]
name = "keyData"
version = "0.1.0"
description = "A tiny client for pushing and getting memo data by key."
readme = "README.md"
requires-python = ">=3.9"
dependencies = [
    "requests>=2.31",
]
```

Recommended flat source configuration:

```toml
[tool.setuptools]
package-dir = {"" = "src"}
py-modules = ["keyData", "config"]
```

Add optional development dependencies for local testing and formatting:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8",
    "responses>=0.25",
    "ruff>=0.5",
]
```

Add Ruff configuration:

```toml
[tool.ruff]
line-length = 88
target-version = "py39"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]
```

This keeps the library installable with:

```bash
pip install git+https://github.com/<owner>/<repo>.git
```

Do not use `uv` for this project. Use Python's built-in virtual environment support:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Python 3.9 compatibility requirements:

- Set `requires-python = ">=3.9"`.
- Do not use `str | None`, `dict | None`, or other PEP 604 union syntax.
- Use `Optional[...]`, `Union[...]`, and other imports from `typing` where needed.
- Avoid syntax introduced after Python 3.9, such as `match` statements.
- Configure tooling with `target-version = "py39"`.

## Configuration Plan

Create `src/config.py`:

```python
BASE_URL = "https://example.com"
```

Implementation details:

- Keep `BASE_URL` as the default server URL.
- Allow both `push` and `get` to accept an optional `url` override for tests and advanced callers.
- Strip trailing slashes from the base URL before constructing request URLs.

## URL and Request Contract

For both functions, the endpoint is:

```text
{base_url}/memo/{key}
```

### `get`

`get(key, token, url=None)` should send:

```text
GET {base_url}/memo/{key}
Authorization: Bearer {token}
```

Implementation expectations:

- Use the `GET` method.
- Pass the token only in the `Authorization` header: `headers={"Authorization": f"Bearer {token}"}`.
- Do not put the token in the URL query string.
- Return the parsed JSON response if the response body is JSON.
- Raise an HTTP-related exception for non-2xx responses.

### `push`

`push(key, value, token, url=None)` should send:

```text
POST {base_url}/memo/{key}
```

With Authorization header:

```text
Authorization: Bearer {token}
```

And POST JSON body containing:

```json
{
  "value": {
    "...": "..."
  }
}
```

Implementation expectations:

- Use the `POST` method.
- The caller must provide `value` as a Python dictionary.
- Do not accept a string, bytes, list, tuple, or already dumped JSON.
- Convert the dictionary to JSON inside the library.
- Pass the token only in the `Authorization` header: `headers={"Authorization": f"Bearer {token}"}`.
- Do not put the token in the URL query string or JSON body.
- Send the request with JSON encoding, for example `requests.post(..., json=payload)`.
- Raise an HTTP-related exception for non-2xx responses.
- Return the parsed JSON response if the response body is JSON.

## Validation Rules

Implement validation before making HTTP requests.

### Shared validation

- `key` must be a non-empty string.
- `token` must be a non-empty string.
- `url`, if provided, must be a non-empty string.

### `push` value validation

- `value` must be a dictionary.
- `value` must be JSON serializable.
- The JSON-encoded size of `value` must be at most 1 kilobyte.
- Use UTF-8 byte size, not Python character length.
- Suggested limit constant:

```python
MAX_VALUE_BYTES = 1024
```

Suggested size check:

```python
json_bytes = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
if len(json_bytes) > MAX_VALUE_BYTES:
    raise ValueError("value JSON payload must be at most 1024 bytes")
```

Recommended errors:

- `TypeError` when `value` is not a dictionary.
- `ValueError` when JSON serialization fails or size exceeds 1 KB.
- `ValueError` when `key`, `token`, or `url` are invalid.

## Implementation Plan

Implement in `src/keyData.py`.

Suggested internal helpers:

- `_build_url(base_url, key)`: returns `{base_url}/memo/{key}`.
- `_validate_key(key)`: validates `key`.
- `_validate_token(token)`: validates `token`.
- `_build_auth_headers(token)`: returns `{"Authorization": f"Bearer {token}"}`.
- `_validate_base_url(url)`: validates and normalizes `url`.
- `_validate_value(value)`: checks dictionary type, JSON serializability, and 1 KB limit.
- `_parse_response(response)`: calls `response.raise_for_status()` and returns `response.json()` when possible.

Suggested public functions:

```python
from typing import Optional


def get(key: str, token: str, url: Optional[str] = None) -> object:
    ...


def push(key: str, value: dict, token: str, url: Optional[str] = None) -> object:
    ...
```

For Python 3.9 compatibility, use `Optional[str]` from `typing`. Do not use `str | None`.

## Testing Plan

Use `pytest` and `responses` to mock HTTP requests. Do not call a real URL.

Test file:

```text
tests/test_keyData.py
```

Tests to implement:

- `get` sends a `GET` request to `/memo/{key}`.
- `get` sends the token as an `Authorization: Bearer <token>` header.
- `get` does not include the token in query parameters.
- `get` returns parsed JSON from the response body.
- `push` sends a `POST` request to `/memo/{key}`.
- `push` sends the token as an `Authorization: Bearer <token>` header.
- `push` sends JSON containing `value`.
- `push` does not include the token in the JSON body.
- `push` accepts dictionary values.
- `push` rejects string values with `TypeError`.
- `push` rejects non-dictionary values with `TypeError`.
- `push` rejects values whose encoded JSON size is greater than 1024 bytes.
- `push` accepts values whose encoded JSON size is 1024 bytes or less.
- `push` raises `ValueError` for non-JSON-serializable dictionaries.
- Both functions raise for HTTP error responses.
- Both functions validate empty `key`.
- Both functions validate empty `token`.
- Both functions can use the configured `BASE_URL` when `url` is not provided.
- Both functions can use a test override URL when `url` is provided.

Example mock expectations:

```python
responses.add(
    responses.GET,
    "https://mock.test/memo/example",
    json={"value": {"hello": "world"}},
    status=200,
)
```

For POST assertions, inspect the recorded request body:

```python
payload = json.loads(responses.calls[0].request.body)
assert payload == {"value": {"hello": "world"}}
assert responses.calls[0].request.headers["Authorization"] == "Bearer test-token"
```

## Documentation Plan

Create a small `README.md` that includes:

- What `keyData` does.
- How to install from GitHub with `pip`.
- How to create and activate a standard Python virtual environment.
- Basic `push` and `get` examples.
- The 1 KB JSON value limit.
- The requirement that `push` receives a dictionary, not a JSON string.

## Verification Commands

After implementation, run:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

Do not use `uv` for environment creation or dependency installation.

## Open Decisions for Later Implementers

- Confirm the real production `BASE_URL` before replacing the placeholder in `src/config.py`.
- Decide whether non-JSON responses should return raw text or raise a parsing error. The first implementation should prefer parsed JSON because the API is described as JSON-based.
- Decide whether `get` should return the whole server response or only a nested `value` field. The first implementation should return the whole parsed JSON response to avoid guessing the server response schema.

## To-Do Checklist

- [ ] Create `AGENT.md` with instructions to use a standard Python virtual environment.
- [ ] Create `pyproject.toml` with PEP 621 metadata.
- [ ] Create a virtual environment with `python -m venv .venv`.
- [ ] Activate the virtual environment.
- [ ] Install all required project and development dependencies with `python -m pip install -e ".[dev]"`.
- [ ] Set `requires-python = ">=3.9"`.
- [ ] Configure `setuptools` for the flat `src/` module layout.
- [ ] Configure Ruff with `target-version = "py39"`.
- [ ] Add runtime dependency on `requests`.
- [ ] Add optional dev dependencies for `pytest`, `responses`, and `ruff`.
- [ ] Create `src/config.py` with `BASE_URL`.
- [ ] Create `src/keyData.py`.
- [ ] Use Python 3.9-compatible type hints such as `Optional[str]`.
- [ ] Avoid Python 3.10+ syntax such as `str | None` and `match`.
- [ ] Implement `get(key, token, url=None)`.
- [ ] Implement `push(key, value, token, url=None)`.
- [ ] Implement URL construction for `{base_url}/memo/{key}`.
- [ ] Validate `key`.
- [ ] Validate `token`.
- [ ] Build `Authorization: Bearer <token>` headers for both public functions.
- [ ] Validate optional URL override.
- [ ] Validate that `push` receives a dictionary value.
- [ ] Validate that `push` value is JSON serializable.
- [ ] Enforce the 1024-byte JSON size limit for `push` values.
- [ ] Ensure `get` sends token only as a Bearer token Authorization header.
- [ ] Ensure `get` does not send token as a query parameter.
- [ ] Ensure `push` sends token only as a Bearer token Authorization header.
- [ ] Ensure `push` sends only `value` in the JSON POST body.
- [ ] Ensure `push` does not send token in the JSON POST body.
- [ ] Ensure HTTP error responses raise exceptions.
- [ ] Ensure successful JSON responses are parsed and returned.
- [ ] Create `tests/test_keyData.py`.
- [ ] Mock all HTTP calls in tests.
- [ ] Test `get` URL and Authorization header.
- [ ] Test `push` URL and JSON body.
- [ ] Test `push` Authorization header.
- [ ] Test validation errors.
- [ ] Test the 1 KB size boundary.
- [ ] Test HTTP error handling.
- [ ] Test configured default URL behavior.
- [ ] Test URL override behavior.
- [ ] Create `README.md` with install and usage instructions.
- [ ] Confirm README instructions use `venv` and `pip`, not `uv`.
- [ ] Run `python -m pytest`.
- [ ] Run `python -m ruff check .`.
- [ ] Confirm installation works from the local project with `pip install -e ".[dev]"`.
