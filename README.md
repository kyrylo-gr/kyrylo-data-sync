
# kdata

## Warning

This is the front-end part of a personal project. You won't be able to use it without an access token or your own backend. If you're motivated, I can share the backend source privately on request or you can use AI to build a compatible one from this project's spec.

## Installation

`kdata` is a tiny Python client for storing and fetching JSON-compatible dictionary data by key.

Install directly from GitHub with `pip`:

```bash
pip install git+https://github.com/kyrylo-gr/kyrylo-data-sync.git
```

For local development, use Python's standard virtual environment tooling:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Usage

```python
from kdata import get, push

token = "secret-token"

push("example-key", {"status": "ok", "count": 3}, token)
data = get("example-key", token)
```

If a request cannot reach the server, times out, receives a server rejection
such as HTTP 4xx/5xx, or receives invalid JSON, `kdata` emits a `RuntimeWarning`
and returns `None`. These network/server failures are intentionally ignorable so
they do not stop your process. Input validation problems, missing tokens, and
malformed local settings still raise clear exceptions because the request cannot
be built correctly.

If you want every public `kdata` function to raising instead of warning (for example when internet connection fails), enable
suppressed-error mode:

```python
from kdata import set_suppress_errors

set_suppress_errors(False)
```

When suppressed-error mode is enabled, public functions emit a `RuntimeWarning`
and return `None` for errors that would otherwise be raised. Call
`set_suppress_errors(False)` to restore the strict behavior.

You can also save a token for a memo key so you do not need to pass it on every
call:

```python
from kdata import get, push, save_token

save_token("example-key", "secret-token")

push("example-key", {"status": "ok", "count": 3})
data = get("example-key")
```

By default, `save_token` writes a project-local `.kdata.json` file in the
current working directory. This file stores tokens in plaintext, is created with
owner-only permissions where the operating system supports them, and must not be
committed to version control.

When `token` is omitted, `kdata` resolves it in this order:

1. A memo-key-specific environment variable.
2. The project-local `.kdata.json` file.
3. The optional OS keyring integration.

Environment variable names start with `KDATA_TOKEN_`, then use the memo key
uppercased with every non-alphanumeric character replaced by `_`. For
`example-key`, set:

```bash
export KDATA_TOKEN_EXAMPLE_KEY="secret-token"
```

To save to the OS keyring, install the optional dependency and opt in
explicitly:

```bash
python -m pip install "kdata[keyring] @ git+https://github.com/kyrylo-gr/kyrylo-data-sync.git"
```

```python
from kdata import delete_token, save_token

save_token("example-key", "secret-token", storage="keyring")
save_token("example-key", "secret-token", storage="both")
delete_token("example-key", storage="both")
```

You can inspect saved token locations without reading token values:

```python
from kdata import get_saved_tokens, get_token_storage

saved = get_saved_tokens()
# {"example-key": "file"}

storage = get_token_storage("example-key")
# "file", "keyring", "both", or None
```

`get_saved_tokens` can list file tokens and keyring tokens saved through
`kdata`. It cannot enumerate credentials that were added directly to your OS
keyring by another tool, because common keyring APIs only support lookup by
service and username.

The default server URL is configured in `kdata/config.py`. Advanced callers and
tests can override it per call:

```python
push("example-key", {"status": "ok"}, token, url="https://mock.test")
data = get("example-key", token, url="https://mock.test")
```

If your server response is shaped like `{"value": ...}`, use `get_value` to
return only the stored value:

```python
from kdata import get_value

value = get_value("example-key", token)
```

## Async Usage

Async wrappers are available for the same front-facing functions:

```python
import kdata.aio as kdata

await kdata.push("example-key", {"status": "ok"}, token)
data = await kdata.get("example-key", token)
```

## Value Rules

`push` accepts a Python dictionary, not a JSON string. The dictionary must be
JSON serializable, and its UTF-8 JSON-encoded size must be at most 1024 bytes.
